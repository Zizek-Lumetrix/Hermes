import json
from unittest.mock import MagicMock
from hermes.pipeline.assess import apply_rules, assess_item, assess_items


def test_rules_reject_short_content():
    assert not apply_rules({"content": "short"})


def test_rules_accept_long_content():
    item = {"content": "x" * 200}
    assert apply_rules(item)


def test_assess_item_successful():
    item = {
        "id": "abc123",
        "title": "New AI Safety Framework Released",
        "content": "NIST published a comprehensive AI safety framework with guidelines "
                   "for testing and evaluating large language models. The framework "
                   "includes red-teaming standards and transparency requirements.",
        "source": "NIST",
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(choices=[
        MagicMock(message=MagicMock(content=json.dumps({
            "relevant": True,
            "domain": "大模型安全",
            "title_cn": "NIST发布AI安全框架",
            "summary": "NIST发布了综合性AI安全框架，包含红队测试和透明度要求。信源为政府机构，权威性较高。",
            "key_points": ["框架涵盖风险评估", "包括实施指南", "透明度要求可能增加合规成本"],
            "implications": "从业者应关注合规要求",
            "confidence": "high",
            "entities": [
                {"name": "NIST", "type": "ORG"},
                {"name": "AI Safety Framework", "type": "CONCEPT"},
            ],
            "prediction": None,
            "exploit_score": 8,
        })))
    ])

    result = assess_item(item, ["大模型安全", "AI编程工具", "能源安全"], mock_client)
    assert result is not None
    assert result["status"] == "assessed"
    analysis = json.loads(result["analysis"])
    assert analysis["title_cn"] == "NIST发布AI安全框架"
    assert analysis["confidence"] == "high"
    entities = json.loads(result["entities"])
    assert len(entities) == 2
    assert result["prediction"] is None
    assert result["exploit_score"] == 0.8
    assert result["domain"] == "大模型安全"


def test_assess_item_not_relevant():
    item = {
        "id": "xyz",
        "title": "Local Sports Game",
        "content": "The local team won the championship. " + "x" * 200,
        "source": "Local News",
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(choices=[
        MagicMock(message=MagicMock(content='{"relevant": false}'))
    ])

    result = assess_item(item, ["AI编程工具", "能源安全"], mock_client)
    assert result is None
    assert item["status"] == "skipped"


def test_assess_item_with_prediction():
    item = {
        "id": "def456",
        "title": "GPT-5 release timeline",
        "content": "OpenAI CEO announced GPT-5 will launch by December 2026. " + "x" * 200,
        "source": "TechCrunch",
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(choices=[
        MagicMock(message=MagicMock(content=json.dumps({
            "relevant": True,
            "domain": "AI编程工具",
            "title_cn": "OpenAI CEO称GPT-5年底发布",
            "summary": "Sam Altman表示GPT-5将在2026年12月前发布。",
            "key_points": ["时间线承诺需验证", "可能影响竞争格局"],
            "implications": "关注实际发布时间",
            "confidence": "medium",
            "entities": [{"name": "Sam Altman", "type": "PERSON"}],
            "prediction": {
                "statement": "GPT-5 will release by December 2026",
                "deadline": "2026-12-31",
                "outcome_var": "GPT-5 public release announcement",
            },
            "exploit_score": 6,
        })))
    ])

    result = assess_item(item, ["AI编程工具", "大模型安全", "能源安全"], mock_client)
    assert result is not None
    pred = json.loads(result["prediction"])
    assert pred["statement"] == "GPT-5 will release by December 2026"
    assert pred["deadline"] == "2026-12-31"
    assert result["exploit_score"] == 0.6


def test_assess_item_parse_error_returns_none():
    item = {
        "id": "bad",
        "title": "Test",
        "content": "x" * 200,
        "source": "Test",
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(choices=[
        MagicMock(message=MagicMock(content="not valid json {{{"))
    ])

    result = assess_item(item, ["AI"], mock_client)
    assert result is None


def test_assess_items_parallel():
    items = [
        {"id": "1", "title": "Short", "content": "x", "source": "Test"},
        {"id": "2", "title": "AI Paper", "content": "x" * 200, "source": "ArXiv"},
        {"id": "3", "title": "Energy News", "content": "x" * 200, "source": "Reuters"},
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(choices=[
        MagicMock(message=MagicMock(content=json.dumps({
            "relevant": True,
            "domain": "能源安全",
            "title_cn": "能源新闻",
            "summary": "测试摘要",
            "key_points": ["要点1"],
            "implications": "启示",
            "confidence": "medium",
            "entities": [],
            "prediction": None,
            "exploit_score": 5,
        })))
    ])

    result = assess_items(items, ["AI", "能源安全"], mock_client, max_workers=2)
    assert len(result) == 2
    assert items[0]["status"] == "skipped"  # short content
    assert all(r["status"] == "assessed" for r in result)


def test_assess_exploit_score_clamped():
    item = {
        "id": "high",
        "title": "High score",
        "content": "x" * 200,
        "source": "Test",
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(choices=[
        MagicMock(message=MagicMock(content=json.dumps({
            "relevant": True,
            "domain": "AI编程工具",
            "title_cn": "测试",
            "summary": "摘要",
            "key_points": ["要点"],
            "implications": "启示",
            "confidence": "high",
            "entities": [],
            "prediction": None,
            "exploit_score": 12,
        })))
    ])

    result = assess_item(item, ["AI编程工具"], mock_client)
    assert result["exploit_score"] == 1.0
