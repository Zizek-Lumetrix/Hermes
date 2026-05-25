import json
from unittest.mock import MagicMock
from hermes.pipeline.analyze import analyze_items, build_analyze_prompt


def test_build_analyze_prompt():
    prompt = build_analyze_prompt(["AI安全"])
    assert "批判性分析" in prompt
    assert "偏见" in prompt
    assert "confidence" in prompt


def test_analyze_items_calls_api_and_parses_response():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({
                    "title_cn": "GPT-5安全漏洞分析",
                    "summary": "研究人员发现GPT-5存在提示注入漏洞，攻击者可绕过安全限制。"
                              "但该研究仅在实验室环境验证，尚未在实际部署中复现。",
                    "key_points": ["提示注入漏洞", "实验室环境验证", "实际影响待确认"],
                    "implications": "AI应用开发者需关注提示注入防御机制，但不需立即恐慌",
                    "confidence": "medium",
                })
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    items = [
        {
            "id": "abc",
            "title": "GPT-5 Security Analysis",
            "content": "Full article content here.",
            "source": "AI Security Blog",
            "relevance_score": 8,
        }
    ]

    result = analyze_items(items, ["AI安全"], mock_client)

    assert len(result) == 1
    assert result[0]["analysis"] is not None
    analysis = json.loads(result[0]["analysis"])
    assert analysis["confidence"] == "medium"
    assert "GPT-5" in analysis["title_cn"]
    assert len(analysis["key_points"]) == 3
    assert result[0]["status"] == "analyzed"


def test_analyze_items_handles_error_gracefully():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API error")

    items = [
        {"id": "x", "title": "T", "content": "C", "source": "S", "relevance_score": 5}
    ]

    result = analyze_items(items, ["AI"], mock_client)
    assert len(result) == 1
    assert result[0]["status"] == "skipped"
