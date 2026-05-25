import requests


def format_summary(logs: list[dict]) -> str:
    lines = ["Hermes Run Summary", "=" * 20]
    total_ms = 0
    errors = []

    for log in logs:
        stage = log["stage"]
        status = log["status"].upper() if log["status"] == "error" else log["status"]
        count = log.get("item_count", 0)
        ms = log.get("duration_ms", 0)
        total_ms += ms

        line = f"  {stage}: {status} | {count} items | {ms/1000:.1f}s"
        lines.append(line)

        if log.get("error"):
            errors.append(f"  [{stage}] {log['error']}")

    lines.append("-" * 20)
    lines.append(f"  Total: {total_ms/1000:.1f}s")

    if errors:
        lines.append("")
        lines.append("ERRORS:")
        lines.extend(errors)

    return "\n".join(lines)


def send_slack(webhook_url: str, text: str) -> None:
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json={"text": text}, timeout=10)
    except Exception:
        pass
