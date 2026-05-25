import json
import os
import time
import uuid
from pathlib import Path

from openai import OpenAI

from hermes.config import load_config, Config
from hermes.db import Database
from hermes.embeddings import EmbeddingIndex
from hermes.ingestors.rss import fetch_feed
from hermes.pipeline.dedup import dedup_items
from hermes.pipeline.filter import filter_items
from hermes.pipeline.analyze import analyze_items
from hermes.pipeline.write import write_brief, scan_feedback
from hermes.notify import format_summary, send_slack


def _get_db_path() -> str:
    base = os.path.expanduser("~/.hermes")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "hermes.db")


def run(config_path: str | None = None) -> None:
    config = load_config(config_path)
    db = Database(_get_db_path())
    run_id = str(uuid.uuid4())
    client = OpenAI(
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
    )

    # Stage 1: Ingest
    t0 = time.monotonic()
    all_items = []
    existing_urls = _get_existing_urls(db)
    for src in config.rss_sources:
        try:
            items = fetch_feed(src["url"], src["name"])
            all_items.extend(items)
        except Exception as e:
            db.log_run(run_id, f"ingest:{src['name']}", "error", 0, 0, str(e))

    for item in all_items:
        db.insert_item(
            id=item.id, source=item.source, title=item.title,
            url=item.url, content=item.content,
            published_at=item.published_at,
        )

    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "ingest", "ok", len(all_items), elapsed)

    if not all_items:
        _finish(db, run_id, config, [])
        return

    # Stage 2: Dedup
    t0 = time.monotonic()
    deduped = dedup_items(all_items, existing_urls)
    for item in deduped:
        db.update_item(item.id, simhash=item.simhash, cluster_id=item.cluster_id)
    new_items = deduped
    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "dedup", "ok", len(new_items), elapsed)

    if not new_items:
        _finish(db, run_id, config, [])
        return

    # Stage 3: Filter
    t0 = time.monotonic()
    feedback = db.get_all_feedback()
    new_item_dicts = [
        {
            "id": i.id, "title": i.title, "content": i.content,
            "cluster_id": i.cluster_id, "source": i.source,
        }
        for i in new_items
    ]
    filtered = filter_items(new_item_dicts, config.domains, feedback, client)
    for item in filtered:
        db.update_item(
            item["id"],
            status=item["status"],
            relevance_score=item["relevance_score"],
            relevance_reason=item.get("relevance_reason", ""),
        )
    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "filter", "ok", len(filtered), elapsed)

    # Stage 4: Analyze
    to_analyze = [f for f in filtered if f["status"] == "filtered"]
    t0 = time.monotonic()
    analyzed = analyze_items(to_analyze, config.domains, client)
    for item in analyzed:
        db.update_item(
            item["id"],
            status=item["status"],
            analysis=item.get("analysis", ""),
        )
    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "analyze", "ok", len(analyzed), elapsed)

    # Stage 5: Write
    written = [a for a in analyzed if a["status"] == "analyzed"]
    t0 = time.monotonic()

    # Build embedding index and link notes
    index = EmbeddingIndex()
    index.build(config.obsidian_vault_path)

    # Scan feedback from previous briefs
    brief_feedback = scan_feedback(
        config.obsidian_vault_path, config.brief_folder
    )
    for fb in brief_feedback:
        db.insert_feedback(fb["brief_date"], fb["rating"])

    for item in written:
        if item.get("analysis"):
            try:
                analysis = json.loads(item["analysis"])
                query_text = analysis.get("title_cn", item.get("title", ""))
            except (json.JSONDecodeError, TypeError):
                query_text = item.get("title", "")
            related = index.query(query_text)
            item["linked_notes"] = json.dumps([r[0] for r in related])

    # Fetch full items from DB for writer
    write_items = []
    for item in written:
        db_item = db.get_items_by_status("analyzed")
        matching = [d for d in db_item if d["id"] == item["id"]]
        if matching:
            write_items.append(dict(matching[0]))
        else:
            write_items.append(item)

    brief_path = write_brief(
        write_items, config.obsidian_vault_path, config.brief_folder
    )

    for item in written:
        db.update_item(item["id"], status="written")

    elapsed = int((time.monotonic() - t0) * 1000)
    db.log_run(run_id, "write", "ok", len(written), elapsed)

    _finish(db, run_id, config, written)


def _get_existing_urls(db: Database) -> set[str]:
    rows = db.conn.execute("SELECT url FROM items").fetchall()
    return {r["url"] for r in rows}


def _finish(db: Database, run_id: str, config, items: list[dict]) -> None:
    logs = db.get_run_logs(run_id)
    summary = format_summary(logs)
    print(summary)
    send_slack(config.slack_webhook, summary)


def status() -> None:
    db = Database(_get_db_path())
    run_id = db.get_last_successful_run()
    if run_id:
        logs = db.get_run_logs(run_id)
        print(format_summary(logs))
    else:
        print("No successful runs yet.")
