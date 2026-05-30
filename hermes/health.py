import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
from typing import List, Optional


def format_health_email(config, ingest_count: int, new_conclusions: int,
                        errors: List[str]) -> MIMEMultipart:
    today = date.today().isoformat()
    msg = MIMEMultipart()
    msg["From"] = config.email_from
    msg["To"] = config.email_to
    msg["Subject"] = f"Hermes Weekly Health Check – {today}"

    body = f"""Hermes Pipeline Health Report
{'=' * 30}

Period ending: {today}

Pipeline Activity:
  Items ingested: {ingest_count}
  New conclusions: {new_conclusions}

Domains tracked: {', '.join(config.domains)}
"""

    if errors:
        body += f"\nErrors ({len(errors)}):\n"
        for e in errors[:5]:
            body += f"  - {e}\n"

    body += f"\nView full status: http://localhost:8000\n"

    msg.attach(MIMEText(body, "plain"))
    return msg


def send_health_check(config, ingest_count: int = 0, new_conclusions: int = 0,
                      errors: Optional[List[str]] = None) -> None:
    try:
        msg = format_health_email(config, ingest_count, new_conclusions, errors or [])
        with smtplib.SMTP(config.email_smtp_host, config.email_smtp_port) as server:
            server.starttls()
            if config.email_password:
                server.login(config.email_from, config.email_password)
            server.send_message(msg)
    except Exception:
        pass
