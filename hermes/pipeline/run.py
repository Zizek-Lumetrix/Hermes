import json
import os
import time
import uuid
from typing import Any

import numpy as np
from openai import OpenAI

from hermes.config import load_config
from hermes.db import Database
from hermes.embeddings import StreamingClusterer
from hermes.ingestors.rss import fetch_feed, RawItem
from hermes.pipeline.dedup import dedup_items
from hermes.pipeline.enrich import enrich_items
from hermes.pipeline.assess import assess_items
from hermes.pipeline.synthesize import synthesize_items, match_conclusion
from hermes.pipeline.backtest import backtest_predictions


def run(config_path: str | None = None, trigger_type: str = "manual") -> None:
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
            db.log_run(run_id, f"ingest:rss:{src.name}", "error", 0, 0, str(e), trigger_type=trigger_type)

    for item in all_items:
        db.insert_item(
            id=item.id, source=item.source, title=item.title,
            url=item.url, content=item.content, published_at=item.published_at,
        )

    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "ingest", "ok", len(all_items), elapsed, trigger_type=trigger_type)

    if not all_items and not db._query("SELECT 1 FROM items WHERE status = 'assessed' AND embedding IS NOT NULL LIMIT 1"):
        _finish(db, run_id, trigger_type)
        return

    # Stage 2: Enrich
    t0 = time.monotonic()
    new_items = db.get_items_for_enrich()
    clusterer = StreamingClusterer(distance_threshold=config.enrich_cluster_distance)

    # Cold start: seed centroids from existing enriched items
    existing_rows = db._query(
        "SELECT embedding FROM items WHERE embedding IS NOT NULL LIMIT 200"
    )
    existing_embeddings = [r["embedding"] for r in existing_rows if r.get("embedding") is not None]
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
    db.log_run(run_id, "enrich", "ok", len(enriched), elapsed, trigger_type=trigger_type)

    if not enriched and not db._query("SELECT 1 FROM items WHERE status = 'assessed' AND embedding IS NOT NULL LIMIT 1"):
        _finish(db, run_id, trigger_type)
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
    db.log_run(run_id, "dedup", "ok", len(deduped), elapsed, trigger_type=trigger_type)

    # Stage 4: Assess (unified prefilter + analyze + postfilter)
    t0 = time.monotonic()
    to_assess = [i for i in enriched if i["status"] == "enriched"]
    assessed = assess_items(to_assess, config.domains, client)
    for item in assessed:
        db.update_item(
            item["id"],
            status=item["status"],
            analysis=item.get("analysis", ""),
            entities=item.get("entities", ""),
            prediction=item.get("prediction"),
            exploit_score=item.get("exploit_score", 0),
            domain=item.get("domain", ""),
            domain_proposed=item.get("domain_proposed"),
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
    # Mark skipped items in DB
    for item in to_assess:
        if item["status"] == "skipped":
            db.update_item(item["id"], status="skipped")

    elapsed = int((time.monotonic() - t0) * 1000)
    analyzed_count = len(assessed)
    db.log_run(run_id, "assess", "ok", analyzed_count, elapsed, trigger_type=trigger_type)

    if not assessed:
        # No new items assessed this run; process previously assessed items
        rows = db._query(
            "SELECT * FROM items WHERE status = 'assessed' AND embedding IS NOT NULL"
        )
        assessed = [dict(r) for r in rows]
    if not assessed:
        _finish(db, run_id, trigger_type)
        return

    # Stage 4.5: Compute surprise scores
    t0 = time.monotonic()
    existing_for_surprise = db.get_active_conclusions_with_embeddings()
    domain_conclusions: dict[str, list[tuple[list[float], float]]] = {}
    for c in existing_for_surprise:
        emb = c.get("embedding")
        dom = c.get("domain", "")
        if emb is not None and dom:
            domain_conclusions.setdefault(dom, []).append((emb, c.get("confidence", 0.5)))

    for item in assessed:
        item_emb = item.get("embedding")
        item_domain = item.get("domain", "")
        if item_emb is None or not item_domain:
            item["surprise_score"] = 0.5
            db.update_item(item["id"], surprise_score=0.5)
            continue

        candidates = domain_conclusions.get(item_domain, [])
        if not candidates:
            item["surprise_score"] = 1.0
            db.update_item(item["id"], surprise_score=1.0)
            continue

        max_sim = 0.0
        vec = np.array(item_emb, dtype=np.float32)
        vec = vec / np.linalg.norm(vec)
        for emb, _ in candidates:
            cand = np.array(emb, dtype=np.float32)
            cand = cand / np.linalg.norm(cand)
            sim = float(np.dot(vec, cand))
            if sim > max_sim:
                max_sim = sim

        surprise = round(1.0 - max_sim, 2)
        item["surprise_score"] = surprise
        db.update_item(item["id"], surprise_score=surprise)

    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "surprise", "ok", len(assessed), elapsed, trigger_type=trigger_type)

    # Stage 5: Synthesize
    t0 = time.monotonic()
    stats = db.get_confirmation_stats()
    feedback = None
    if stats["total"] > 0:
        confirmed_pct = stats["confirmed"] / stats["total"] * 100
        feedback = (
            f"历史反馈提醒：你之前提出了 {stats['total']} 条预测性结论，"
            f"其中 {stats['confirmed']} 条已被确认（{confirmed_pct:.0f}%），"
            f"{stats['challenged']} 条被质疑。"
            f"{stats['unmarked']} 条尚未审核。"
            f"请参考这些反馈来调整你的判断尺度——如果准确率较低，请更严格地判断什么是可验证的预测。"
        )
    synthesis = synthesize_items(assessed, config.domains, client, min_score=0.3,
                                  feedback_context=feedback)
    if synthesis:
        # Load existing conclusions for cross-run matching
        existing_conclusions = db.get_active_conclusions_with_embeddings()

        # Build cluster lookup: short_id -> full item IDs in the same cluster
        clusters = synthesis.pop("_clusters", [])
        cluster_map: dict[str, list[str]] = {}
        for cl in clusters:
            for item_id in cl:
                short = item_id[:12]
                cluster_map.setdefault(short, []).append(item_id)

        for theme in synthesis.get("themes", []):
            related_items = []
            seen_ids = set()
            for short_id in theme.get("related_item_ids", []):
                full_ids = cluster_map.get(short_id, [short_id])
                for fid in full_ids:
                    if fid not in seen_ids:
                        seen_ids.add(fid)
                        matching = [i for i in assessed if i["id"].startswith(fid[:12])]
                        related_items.extend(matching)

            if not related_items:
                continue

            # Determine domain from related items (use domain assigned by assess)
            domains_seen: dict[str, int] = {}
            for item in related_items:
                d = item.get("domain", "")
                if d:
                    domains_seen[d] = domains_seen.get(d, 0) + 1
            domain = max(domains_seen, key=domains_seen.get) if domains_seen else config.domains[0]

            # Compute embedding as mean of related item embeddings
            item_embs = [item["embedding"] for item in related_items if item.get("embedding") is not None]
            if item_embs:
                mean_emb = np.mean(np.array(item_embs), axis=0).tolist()
            else:
                mean_emb = [0.0] * 384

            # Compute confidence from evidence
            confidence_map = {"high": 0.85, "medium": 0.6, "low": 0.35}
            weights = []
            bases = []
            for item in related_items:
                try:
                    analysis = json.loads(item.get("analysis", "{}"))
                except (json.JSONDecodeError, TypeError):
                    analysis = {}
                bases.append(confidence_map.get(analysis.get("confidence", "medium"), 0.5))
                weights.append(max(0.2, item.get("exploit_score", 0.5)))
            total_w = sum(weights) if weights else 1.0
            avg_conf = sum(b * w for b, w in zip(bases, weights)) / total_w
            n = len(related_items)
            size_factor = min(1.12, 0.6 + 0.12 * min(n, 4) + 0.02 * max(0, n - 4))
            confidence = round(min(0.95, avg_conf * size_factor), 2)

            # Cross-run matching
            matched_id, action = match_conclusion(mean_emb, confidence, existing_conclusions)

            if action == "new":
                conclusion_id = str(uuid.uuid4())
            else:
                conclusion_id = matched_id
                if action == "update":
                    # Blend confidence slightly toward new evidence
                    existing = db.get_conclusion(matched_id)
                    if existing:
                        confidence = round((existing["confidence"] + confidence) / 2, 2)

            counter = theme.get("counter_evidence", "")
            desc = theme.get("summary", "")
            if counter:
                desc = desc + "\n\n反对意见: " + counter

            ctype = theme.get("conclusion_type", "descriptive")
            if ctype not in ("predictive", "evaluative", "descriptive"):
                ctype = "descriptive"

            db.upsert_conclusion(
                id=conclusion_id,
                statement=theme.get("title", ""),
                domain=domain,
                confidence=confidence,
                embedding=mean_emb,
                change_description=desc,
                triggered_by=[{"item_id": item["id"][:12]} for item in related_items],
                conclusion_type=ctype,
            )

            if action == "update":
                for item in related_items:
                    db.add_triggered_by(conclusion_id, item["id"])

            for item in related_items:
                db.update_item(item["id"], status="incorporated")

    elapsed = int((time.monotonic() - t0) * 1000)
    theme_count = len(synthesis.get("themes", [])) if synthesis else 0
    db.log_run(run_id, "synthesize", "ok", theme_count, elapsed, trigger_type=trigger_type)

    # Stage 6: Backtest
    t0 = time.monotonic()
    pending = db.get_pending_predictions()
    if pending:
        backtest_results = backtest_predictions(pending, client, confirmation_stats=stats)
        for result in backtest_results:
            db.update_prediction_result(result["id"], result["result"], result["reason"])
    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "backtest", "ok", len(pending), elapsed, trigger_type=trigger_type)

    _finish(db, run_id, trigger_type)


def _finish(db: Database, run_id: str, trigger_type: str = "manual") -> None:
    if trigger_type != "cron":
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
