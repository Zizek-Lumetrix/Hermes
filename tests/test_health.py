from unittest.mock import MagicMock, patch
from hermes.health import format_health_email, send_health_check


def test_format_health_email():
    config = MagicMock()
    config.email_from = "hermes@test.com"
    config.email_to = "user@test.com"
    config.domains = ["AI", "能源"]

    msg = format_health_email(config, ingest_count=42, new_conclusions=3, errors=[])
    assert "Hermes Weekly Health Check" in msg["Subject"]
    # Decode the text/plain payload to verify body content
    text_part = msg.get_payload()[0]
    body = text_part.get_payload(decode=True).decode("utf-8")
    assert "Items ingested: 42" in body
    assert "New conclusions: 3" in body


@patch("smtplib.SMTP")
def test_send_health_check_sends_email(mock_smtp):
    config = MagicMock()
    config.email_smtp_host = "smtp.test.com"
    config.email_smtp_port = 587
    config.email_from = "hermes@test.com"
    config.email_to = "user@test.com"
    config.email_password = None

    send_health_check(config, ingest_count=10, new_conclusions=1, errors=[])
    assert mock_smtp.called


@patch("smtplib.SMTP")
def test_send_health_check_silently_fails(mock_smtp):
    mock_smtp.side_effect = Exception("Connection refused")
    config = MagicMock()
    config.email_smtp_host = "bad.host"
    config.email_smtp_port = 587
    config.email_from = "h@t.com"
    config.email_to = "u@t.com"
    config.email_password = None

    # Should not raise
    send_health_check(config, ingest_count=0, new_conclusions=0, errors=["test error"])
