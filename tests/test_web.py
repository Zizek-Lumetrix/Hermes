from unittest.mock import MagicMock
from fastapi.testclient import TestClient


def test_graph_endpoint(monkeypatch):
    mock_db = MagicMock()
    mock_db.get_all_conclusions.return_value = [
        {"id": "c1", "statement": "AI is advancing", "domain": "AI",
         "confidence": 0.8, "user_confirmation": None, "status": "active",
         "created_at": "2026-05-01T00:00:00Z"},
    ]
    mock_db.get_conclusion_versions.return_value = []

    monkeypatch.setattr("hermes.web.app.get_db", lambda: mock_db)

    from hermes.web.app import app
    client = TestClient(app)
    response = client.get("/api/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data


def test_stream_endpoint(monkeypatch):
    mock_db = MagicMock()
    mock_db._query.return_value = [
        {"run_id": "r1", "stage": "analyze", "status": "ok", "item_count": 5,
         "duration_ms": 1000, "error": None, "created_at": "2026-05-30T10:00:00Z"},
    ]

    monkeypatch.setattr("hermes.web.app.get_db", lambda: mock_db)

    from hermes.web.app import app
    client = TestClient(app)
    response = client.get("/api/stream")
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data


def test_predictions_endpoint(monkeypatch):
    mock_db = MagicMock()
    mock_db.get_all_predictions.return_value = [
        {"id": "p1", "item_id": "i1", "statement": "Something will happen",
         "deadline": "2026-06-01", "outcome_var": "observable",
         "backtest_result": None, "backtest_reason": None, "backtest_at": None},
    ]

    monkeypatch.setattr("hermes.web.app.get_db", lambda: mock_db)

    from hermes.web.app import app
    client = TestClient(app)
    response = client.get("/api/predictions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_health_endpoint(monkeypatch):
    mock_db = MagicMock()
    monkeypatch.setattr("hermes.web.app.get_db", lambda: mock_db)

    from hermes.web.app import app
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
