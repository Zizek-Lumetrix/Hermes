import json
import os
import time
import uuid
from typing import Any

from openai import OpenAI

from hermes.config import load_config
from hermes.db import Database
from hermes.embeddings import StreamingClusterer
from hermes.ingestors.rss import fetch_feed, RawItem
from hermes.ingestors.obsidian import read_vault
from hermes.pipeline.dedup import dedup_items
from hermes.pipeline.enrich import enrich_items
from hermes.pipeline.prefilter import prefilter_items
from hermes.pipeline.analyze import analyze_items
from hermes.pipeline.postfilter import score_items
from hermes.pipeline.synthesize import synthesize_items
from hermes.pipeline.backtest import backtest_predictions


def run(config_path: str | None = None) -> None:
    config = load_config(config_path)
    db = Database(config.db_url)
    run_id = str(uuid.uuid4())
    client = OpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)

    # Stage 1: Ingest
    t0 = time.monotonic()
    existing_urls = db.get_existing_urls()
    all_items: list[Any] = []

    active_sources = [s for s in config.rss_sources if s.enabled]
    for src in active_sources:
        try:
            items = fetch_feed(src.url, src.name)
            all_items.extend(items)
        except Exception as e:
            db.log_run(run_id, f"ingest:rss:{src.name}", "error", 0, 0, str(e))

    vault_items = read_vault(config.obsidian_vault_path)
    all_items.extend(vault_items)

    for item in all_items:
        db.insert_item(
            id=item.id, source=item.source, title=item.title,
            url=item.url, content=item.content, published_at=item.published_at,
        )

    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "ingest", "ok", len(all_items), elapsed)

    if not all_items:
        _finish(db, run_id)
        return

    # Stage 2: Enrich
    t0 = time.monotonic()
    new_items = db.get_items_for_enrich()
    clusterer = StreamingClusterer(distance_threshold=config.enrich_cluster_distance)

    # Cold start: seed centroids from existing enriched items
    existing_rows = db._query(
        "SELECT embedding FROM items WHERE embedding IS NOT NULL LIMIT 200"
    )
    existing_embeddings = [r["embedding"] for r in existing_rows if r.get("embedding")]
    if existing_embeddings:
        clusterer.cold_start(existing_embeddings)

    item_dicts = [dict(i) for i in new_items]
    enriched = enrich_items(item_dicts, clusterer)
    for item in enriched:
        db.update_item(
            item["id"],
            embedding=item["embedding"],
            implicit_cluster=item["implicit_cluster"],
            status="enriched",
        )

    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "enrich", "ok", len(enriched), elapsed)

    if not enriched:
        _finish(db, run_id)
        return

    # Stage 3: Dedup
    t0 = time.monotonic()
    raw_items = []
    for i in enriched:
        r = RawItem(
            id=i["id"], source=i.get("source", ""),
            title=i.get("title", ""), url=i.get("url", ""),
            content=i.get("content", ""),
            published_at=i.get("published_at"),
        )
        raw_items.append(r)

    deduped = dedup_items(raw_items, existing_urls)
    for item in deduped:
        db.update_item(item.id, fingerprint=item.simhash, cluster_id=item.cluster_id)

    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "dedup", "ok", len(deduped), elapsed)

    # Stage 4: Pre-filter
    t0 = time.monotonic()
    to_filter = [i for i in enriched if i["status"] == "enriched"]
    filtered = prefilter_items(to_filter, config.domains, client)
    for item in filtered:
        db.update_item(item["id"], status=item["status"])
    for item in to_filter:
        if item["status"] == "skipped":
            db.update_item(item["id"], status="skipped")

    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "prefilter", "ok", len(filtered), elapsed)

    if not filtered:
        _finish(db, run_id)
        return

    # Stage 5: Analyze
    t0 = time.monotonic()
    analyzed = analyze_items(filtered, config.domains, client)
    for item in analyzed:
        db.update_item(
            item["id"],
            status=item["status"],
            analysis=item.get("analysis", ""),
            entities=item.get("entities", ""),
            prediction=item.get("prediction"),
        )
        if item.get("prediction"):
            try:
                pred = json.loads(item["prediction"])
                if pred and pred.get("statement") and pred.get("deadline"):
                    db.insert_prediction(
                        item_id=item["id"],
                        statement=pred["statement"],
                        deadline=pred["deadline"],
                        outcome_var=pred.get("outcome_var"),
                    )
            except (json.JSONDecodeError, TypeError):
                pass

    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "analyze", "ok", len(analyzed), elapsed)

    # Stage 6: Post-filter
    t0 = time.monotonic()
    scored = score_items(analyzed, config.domains, client)
    for item in scored:
        db.update_item(item["id"], exploit_score=item["exploit_score"], status="scored")

    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "postfilter", "ok", len(scored), elapsed)

    # Stage 7: Synthesize
    t0 = time.monotonic()
    synthesis = synthesize_items(scored, config.domains, client, min_score=0.3)
    if synthesis:
        for theme in synthesis.get("themes", []):
            for short_id in theme.get("related_item_ids", []):
                matching = [i for i in scored if i["id"].startswith(short_id)]
                for m in matching:
                    db.update_item(m["id"], status="incorporated")
    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "synthesize", "ok", 1 if synthesis else 0, elapsed)

    # Stage 8: Backtest
    t0 = time.monotonic()
    pending = db.get_pending_predictions()
    if pending:
        backtest_results = backtest_predictions(pending, client)
        for result in backtest_results:
            db.update_prediction_result(result["id"], result["result"], result["reason"])
    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "backtest", "ok", len(pending), elapsed)

    _finish(db, run_id)


def _finish(db: Database, run_id: str) -> None:
    logs = db.get_run_logs(run_id)
    from hermes.notify import format_summary
    print(format_summary(logs))


def status() -> None:
    config = load_config()
    db = Database(config.db_url)
    run_id = db.get_last_successful_run()
    if run_id:
        logs = db.get_run_logs(run_id)
        from hermes.notify import format_summary
        print(format_summary(logs))
    else:
        print("No successful runs yet.")
