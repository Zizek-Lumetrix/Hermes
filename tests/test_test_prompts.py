import json
from unittest.mock import MagicMock, patch
from hermes.pipeline.test_prompts import (
    _compare_result, _parse_response, run_prompt_tests,
    format_prompt_test_report, load_fixtures,
)


def test_parse_response_valid():
    result = _parse_response('{"relevant": true, "domain": "AI", "title_cn": "测试"}')
    assert result is not None
    assert result["relevant"] is True


def test_parse_response_with_code_block():
    result = _parse_response('```json\n{"relevant": false}\n```')
    assert result is not None
    assert result["relevant"] is False


def test_parse_response_invalid():
    assert _parse_response("not json {{{") is None


def test_compare_result_perfect_match():
    result = {
        "relevant": True, "domain": "AI编程工具",
        "confidence": "high", "exploit_score": 8,
        "title_cn": "测试", "summary": "摘要", "key_points": ["要点"],
        "implications": "启示",
    }
    expected = {"relevant": True, "domain": "AI编程工具"}
    score, issues = _compare_result(result, expected)
    assert score == 5
    assert issues == []


def test_compare_result_relevance_mismatch():
    result = {"relevant": False}
    expected = {"relevant": True}
    score, issues = _compare_result(result, expected)
    assert score < 3
    assert any("relevant" in i for i in issues)


def test_compare_result_missing_fields():
    result = {
        "relevant": True, "domain": "能源安全",
        "confidence": "low", "exploit_score": 3,
    }
    expected = {"relevant": True, "domain": "能源安全"}
    score, issues = _compare_result(result, expected)
    assert score == 4
    assert any("missing" in i for i in issues)


def test_compare_result_invalid_confidence():
    result = {
        "relevant": True, "domain": "AI编程工具",
        "confidence": "uncertain", "exploit_score": 5,
        "title_cn": "测试", "summary": "摘要", "key_points": ["要点"],
        "implications": "启示",
    }
    expected = {"relevant": True, "domain": "AI编程工具"}
    score, issues = _compare_result(result, expected)
    assert score == 4
    assert any("confidence" in i.lower() for i in issues)


def test_load_fixtures_finds_all():
    fixtures = load_fixtures()
    assert len(fixtures) == 10


def test_load_fixtures_with_limit():
    fixtures = load_fixtures(limit=3)
    assert len(fixtures) == 3


def test_format_report_all_pass():
    report = {
        "passed": 2, "total": 2,
        "results": [
            {"fixture": "001", "title": "T1", "score": 5, "issues": [],
             "domain": "AI", "confidence": "high", "exploit_score": 8},
            {"fixture": "002", "title": "T2", "score": 4, "issues": [],
             "domain": "能源", "confidence": "medium", "exploit_score": 6},
        ],
    }
    output = format_prompt_test_report(report)
    assert "PASS" in output
    assert "safe to deploy" in output


def test_format_report_with_failures():
    report = {
        "passed": 1, "total": 2,
        "results": [
            {"fixture": "001", "title": "T1", "score": 5, "issues": [],
             "domain": "AI", "confidence": "high", "exploit_score": 8},
            {"fixture": "002", "title": "T2", "score": 2,
             "issues": ["domain: expected A, got B", "missing fields: summary"],
             "domain": "B", "confidence": "low", "exploit_score": 3},
        ],
    }
    output = format_prompt_test_report(report)
    assert "FAIL" in output
    assert "below threshold" in output


def test_run_prompt_tests_integration():
    """Integration test: run fixtures through prompt with mock LLM."""
    mock_client = MagicMock()

    def mock_create(*args, **kwargs):
        msg = MagicMock()
        msg.choices = [MagicMock(message=MagicMock(
            content=json.dumps({
                "relevant": True, "domain": "AI编程工具",
                "title_cn": "中文标题", "summary": "分析摘要",
                "key_points": ["要点1", "要点2"],
                "implications": "启示内容",
                "confidence": "high",
                "entities": [{"name": "GitHub", "type": "ORG"}],
                "prediction": None,
                "exploit_score": 8,
            })
        ))]
        return msg

    mock_client.chat.completions.create.side_effect = mock_create

    report = run_prompt_tests(mock_client, limit=3, threshold=4)
    assert report["total"] == 3
    assert report["passed"] == 3
