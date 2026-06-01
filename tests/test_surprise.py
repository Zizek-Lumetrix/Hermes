import json
from unittest.mock import MagicMock

import numpy as np

from hermes.pipeline.synthesize import synthesize_items


def test_synthesize_uses_combined_surprise_exploit_score():
    # Items with low exploit but high surprise should pass the filter
    items = [
        {"id": "a", "title": "AI Paper", "source": "ArXiv",
         "analysis": json.dumps({"title_cn": "AI论文", "summary": "关于对齐的研究。", "confidence": "high"}),
         "exploit_score": 0.2, "surprise_score": 0.9, "embedding": [0.1] * 384},
        {"id": "b", "title": "AI Paper 2", "source": "ArXiv",
         "analysis": json.dumps({"title_cn": "AI论文2", "summary": "关于安全的研究。", "confidence": "high"}),
         "exploit_score": 0.3, "surprise_score": 0.8, "embedding": [0.11] * 384},
        {"id": "c", "title": "Oil News", "source": "Reuters",
         "analysis": json.dumps({"title_cn": "油价新闻", "summary": "原油价格上涨。", "confidence": "medium"}),
         "exploit_score": 0.6, "surprise_score": 0.1, "embedding": [0.9] * 384},
    ]

    mock_client = MagicMock()
    m = MagicMock()
    m.choices = [MagicMock(message=MagicMock(content=json.dumps({
        "themes": [
            {"title": "AI安全进展", "summary": "多项AI安全研究取得进展",
             "related_item_ids": ["a", "b"], "significance": "合规要求趋严"},
        ],
        "connections": [],
        "overall_narrative": "AI安全领域持续活跃。",
    })))]
    mock_client.chat.completions.create.return_value = m

    # min_score=0.5, items a (0.2 exploit but 0.9 surprise) and b should pass
    result = synthesize_items(items, ["AI安全", "能源"], mock_client, min_score=0.5)
    assert result is not None
    assert len(result["themes"]) >= 1


def test_surprise_api_endpoint(monkeypatch):
    mock_db = MagicMock()
    mock_db._query.return_value = [
        {"id": "abc", "title": "Unexpected News", "source": "Blog",
         "url": "https://example.com", "domain": "AI",
         "analysis": '{"title_cn":"意外新闻","summary":"摘要"}',
         "entities": '[]', "exploit_score": 0.3, "surprise_score": 0.85,
         "published_at": "2026-06-01T00:00:00Z"},
    ]

    monkeypatch.setattr("hermes.web.app.get_db", lambda: mock_db)

    from fastapi.testclient import TestClient
    from hermes.web.app import app
    client = TestClient(app)
    response = client.get("/api/surprise?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["surprise_score"] == 0.85
    assert data[0]["domain"] == "AI"


def test_surprise_endpoint_empty_db(monkeypatch):
    mock_db = MagicMock()
    mock_db._query.return_value = []
    monkeypatch.setattr("hermes.web.app.get_db", lambda: mock_db)

    from fastapi.testclient import TestClient
    from hermes.web.app import app
    client = TestClient(app)
    response = client.get("/api/surprise")
    assert response.status_code == 200
    assert response.json() == []
