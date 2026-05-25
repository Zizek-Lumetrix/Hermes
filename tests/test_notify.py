from hermes.notify import format_summary


def test_format_summary():
    logs = [
        {"stage": "ingest", "status": "ok", "item_count": 50, "duration_ms": 1200},
        {"stage": "dedup", "status": "ok", "item_count": 30, "duration_ms": 300},
        {"stage": "filter", "status": "ok", "item_count": 8, "duration_ms": 45000},
        {"stage": "analyze", "status": "ok", "item_count": 5, "duration_ms": 30000},
        {"stage": "write", "status": "ok", "item_count": 5, "duration_ms": 2000},
    ]

    summary = format_summary(logs)
    assert "50" in summary
    assert "8" in summary
    assert "5" in summary


def test_format_summary_with_errors():
    logs = [
        {"stage": "ingest", "status": "ok", "item_count": 50, "duration_ms": 1200},
        {"stage": "dedup", "status": "error", "item_count": 0, "duration_ms": 100,
         "error": "database locked"},
    ]

    summary = format_summary(logs)
    assert "ERROR" in summary
    assert "database locked" in summary
