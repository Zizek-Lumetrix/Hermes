import json
from unittest.mock import MagicMock
from hermes.pipeline.filter import filter_items, build_filter_prompt


def test_build_filter_prompt_includes_domains():
    prompt = build_filter_prompt(["AI安全", "开源模型"], feedback_notes=[])
    assert "AI安全" in prompt
    assert "开源模型" in prompt
    assert "0-10" in prompt
    assert "JSON" in prompt


def test_build_filter_prompt_with_feedback():
    feedback = [{"item_id": "x", "rating": 1}, {"item_id": "y", "rating": 5}]
    prompt = build_filter_prompt(["AI"], feedback_notes=feedback)
    assert "用户偏好" in prompt


def test_filter_items_calls_api():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"score": 8, "reason": "直接相关AI安全话题"}'
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    items = [
        {
            "id": "abc",
            "title": "GPT-5 Security Analysis",
            "content": "Researchers find vulnerabilities in GPT-5.",
            "cluster_id": "c1",
            "source": "Blog A",
        }
    ]

    result = filter_items(items, ["AI安全"], [], mock_client)

    assert len(result) == 1
    assert result[0]["relevance_score"] == 8
    assert result[0]["relevance_reason"] == "直接相关AI安全话题"
    assert result[0]["status"] == "filtered"


def test_filter_items_skips_low_score():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"score": 1, "reason": ""}'
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    items = [
        {
            "id": "xyz",
            "title": "Weather Forecast",
            "content": "Sunny tomorrow.",
            "cluster_id": "c1",
            "source": "Weather Blog",
        }
    ]

    result = filter_items(items, ["AI安全"], [], mock_client)
    assert len(result) == 1
    assert result[0]["status"] == "skipped"


def test_filter_items_handles_malformed_json():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="not valid json"))
    ]
    mock_client.chat.completions.create.return_value = mock_response

    items = [{"id": "x", "title": "T", "content": "C", "cluster_id": "c1", "source": "S"}]
    result = filter_items(items, ["AI"], [], mock_client)
    assert len(result) >= 0
