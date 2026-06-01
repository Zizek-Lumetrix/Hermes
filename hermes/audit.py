"""Data quality audit: compare LLM analysis against original content."""

import json
import random

from hermes.db import Database


def run_audit(db: Database, n: int = 5) -> None:
    """Pick N random analyzed items and display side-by-side for manual grading."""
    items = db._query(
        "SELECT id, title, source, url, content, analysis, entities "
        "FROM items WHERE status IN ('assessed', 'incorporated') "
        "ORDER BY random() LIMIT %s",
        (n,),
    )

    if not items:
        print("No analyzed items found. Run the pipeline first.")
        return

    scores_factual = []
    scores_missing = []
    scores_hallucination = []

    for idx, item in enumerate(items, 1):
        try:
            analysis = json.loads(item.get("analysis", "{}"))
        except (json.JSONDecodeError, TypeError):
            analysis = {}

        content_preview = (item.get("content") or "")[:500]

        print(f"\n{'─' * 60}")
        print(f"[{idx}/{len(items)}] {item['title'][:80]}")
        print(f"Source: {item.get('source', 'unknown')}")
        print(f"URL: {item.get('url', 'N/A')}")
        print(f"\n--- Original Content (first 500 chars) ---")
        print(content_preview)
        if len(item.get("content") or "") > 500:
            print("... [truncated]")

        print(f"\n--- LLM Analysis ---")
        print(f"Title (CN): {analysis.get('title_cn', 'N/A')}")
        print(f"Summary: {analysis.get('summary', 'N/A')}")
        print(f"Key Points: {', '.join(analysis.get('key_points', []))}")
        print(f"Implications: {analysis.get('implications', 'N/A')}")
        print(f"Confidence: {analysis.get('confidence', 'N/A')}")

        print(f"\n--- Manual Grading ---")
        factual = _ask_rating("Factual accuracy (1-5, how well does the analysis match the content)?")
        missing = _ask_rating("Missing points (1-5, 5=no important points missed)?")
        hallu = _ask_rating("Hallucinated claims (1-5, 5=no hallucinations detected)?")

        scores_factual.append(factual)
        scores_missing.append(missing)
        scores_hallucination.append(hallu)

    print(f"\n{'═' * 60}")
    print("AUDIT REPORT")
    print(f"{'═' * 60}")
    print(f"Items audited: {len(items)}")
    print(f"Factual accuracy:  {_avg(scores_factual):.1f}/5")
    print(f"Missing detection: {_avg(scores_missing):.1f}/5")
    print(f"No hallucinations: {_avg(scores_hallucination):.1f}/5")
    overall = (_avg(scores_factual) + _avg(scores_missing) + _avg(scores_hallucination)) / 3
    print(f"Overall quality:   {overall:.1f}/5")
    if overall < 4.0:
        print("\n!!! Quality below threshold (4.0/5). Review and fix the assess prompt.")


def _ask_rating(prompt: str) -> float:
    while True:
        try:
            raw = input(f"  {prompt} [1-5]: ").strip()
            val = float(raw)
            if 1 <= val <= 5:
                return val
            print("  Please enter a number between 1 and 5.")
        except (ValueError, EOFError):
            print("  Invalid input.")


def _avg(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0
