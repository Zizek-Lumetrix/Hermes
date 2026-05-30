# hermes/notify.py — kept for backward compat, delegates to health module
from typing import Optional
from hermes.health import send_health_check, format_health_email


def format_summary(logs: list[dict]) -> str:
    lines = ["Hermes Run Summary", "=" * 20]
    total_ms = 0
    for log in logs:
        stage = log.get("stage", "?")
        status = log.get("status", "?")
        count = log.get("item_count", 0)
        ms = log.get("duration_ms", 0)
        total_ms += ms
        lines.append(f"  {stage}: {status} | {count} items | {ms/1000:.1f}s")
    lines.append("-" * 20)
    lines.append(f"  Total: {total_ms/1000:.1f}s")
    return "\n".join(lines)


def send_slack(webhook_url: Optional[str], text: str) -> None:
    pass  # Slack notification removed in v2
