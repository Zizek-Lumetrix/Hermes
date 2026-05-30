import json
from unittest.mock import MagicMock
from hermes.pipeline.analyze import analyze_items


def test_analyze_two_calls():
    items = [
        {
            "id": "abc123",
            "title": "New AI Safety Framework Released",
            "content": "NIST published a comprehensive AI safety framework with guidelines.",
            "source": "NIST",
        },
    ]

    mock_client = MagicMock()
    call1 = MagicMock()
    call1.choices = [MagicMock(message=MagicMock(content=json.dumps({
        "title_cn": "NIST发布AI安全框架",
        "summary": "NIST发布了综合性AI安全框架。",
        "key_points": ["框架涵盖风险评估", "包括实施指南"],
        "implications": "从业者应关注合规要求",
        "confidence": "high",
    })))]
    call2 = MagicMock()
    call2.choices = [MagicMock(message=MagicMock(content=json.dumps({
        "entities": [
            {"name": "NIST", "type": "ORG", "mention_positions": [0]},
            {"name": "AI Safety Framework", "type": "CONCEPT", "mention_positions": [1]},
        ],
        "prediction": None,
    })))]
    mock_client.chat.completions.create.side_effect = [call1, call2]

    result = analyze_items(items, ["AI安全"], mock_client)
    assert len(result) == 1
    assert result[0]["status"] == "analyzed"
    analysis = json.loads(result[0]["analysis"])
    assert analysis["title_cn"] == "NIST发布AI安全框架"
    entities = json.loads(result[0]["entities"])
    assert len(entities) == 2
    assert result[0]["prediction"] is None


def test_analyze_extracts_prediction():
    items = [
        {
            "id": "def456",
            "title": "OpenAI CEO says GPT-5 by end of year",
            "content": "Sam Altman stated that GPT-5 will be released by December 2026.",
            "source": "TechCrunch",
        },
    ]

    mock_client = MagicMock()
    call1 = MagicMock()
    call1.choices = [MagicMock(message=MagicMock(content=json.dumps({
        "title_cn": "OpenAI CEO称GPT-5年底发布",
        "summary": "Sam Altman表示GPT-5将在2026年12月前发布。",
        "key_points": ["时间线承诺", "可能影响竞争格局"],
        "implications": "关注实际发布时间",
        "confidence": "medium",
    })))]
    call2 = MagicMock()
    call2.choices = [MagicMock(message=MagicMock(content=json.dumps({
        "entities": [{"name": "Sam Altman", "type": "PERSON", "mention_positions": [0]}],
        "prediction": {
            "statement": "GPT-5 will release by December 2026",
            "deadline": "2026-12-31",
            "outcome_var": "GPT-5 public release announcement",
        },
    })))]
    mock_client.chat.completions.create.side_effect = [call1, call2]

    result = analyze_items(items, ["AI"], mock_client)
    assert len(result) == 1
    pred = json.loads(result[0]["prediction"])
    assert pred is not None
    assert pred["statement"] == "GPT-5 will release by December 2026"


def test_analyze_parse_failure_skips_item():
    items = [{"id": "bad", "title": "Test", "content": "Content", "source": "Test"}]
    mock_client = MagicMock()
    bad = MagicMock()
    bad.choices = [MagicMock(message=MagicMock(content="not valid json {{{{{"))]
    mock_client.chat.completions.create.return_value = bad

    result = analyze_items(items, ["AI"], mock_client)
    assert len(result) == 0


def test_analyze_missing_required_fields_skips():
    items = [{"id": "partial", "title": "Test", "content": "Content", "source": "Test"}]
    mock_client = MagicMock()
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content='{"title_cn": "Only title"}'))]
    mock_client.chat.completions.create.return_value = resp

    result = analyze_items(items, ["AI"], mock_client)
    assert len(result) == 0
