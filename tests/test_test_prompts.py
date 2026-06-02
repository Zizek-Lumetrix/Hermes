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


# -- Synthesize test runner tests --

def test_load_synthesize_fixtures():
    from hermes.pipeline.test_prompts import load_synthesize_fixtures
    fixtures = load_synthesize_fixtures()
    assert len(fixtures) == 4


def test_load_synthesize_fixtures_with_limit():
    from hermes.pipeline.test_prompts import load_synthesize_fixtures
    fixtures = load_synthesize_fixtures(limit=2)
    assert len(fixtures) == 2


def test_compare_synthesize_result_perfect():
    from hermes.pipeline.test_prompts import _compare_synthesize_result
    result = {
        "themes": [
            {
                "title": "AI编程工具竞争加剧",
                "summary": "多家公司推出AI编程工具",
                "related_item_ids": ["abc123def456"],
                "significance": "改变软件开发范式",
                "counter_evidence": "目前所有工具都在演示阶段，实际部署数据有限",
                "conclusion_type": "evaluative",
            }
        ],
        "connections": [
            {"from_theme": 0, "to_theme": 0, "relationship": "因果关系", "description": "竞争驱动创新"}
        ],
        "overall_narrative": "AI编程工具市场正在快速演变",
    }
    expected = {
        "min_themes": 1,
        "has_counter_evidence": True,
        "has_connections": True,
        "has_narrative": True,
    }
    score, issues = _compare_synthesize_result(result, expected)
    assert score == 6
    assert issues == []


def test_compare_synthesize_result_missing_counter_evidence():
    from hermes.pipeline.test_prompts import _compare_synthesize_result
    result = {
        "themes": [
            {
                "title": "测试主题",
                "summary": "摘要",
                "related_item_ids": ["abc123"],
                "significance": "意义",
                "counter_evidence": "",  # empty!
                "conclusion_type": "descriptive",
            }
        ],
        "connections": [{"from_theme": 0, "to_theme": 0, "relationship": "支撑佐证", "description": "关联"}],
        "overall_narrative": "全局叙事",
    }
    expected = {"has_counter_evidence": True}
    score, issues = _compare_synthesize_result(result, expected)
    assert score < 6
    assert any("counter_evidence" in i for i in issues)


def test_compare_synthesize_result_invalid_conclusion_type():
    from hermes.pipeline.test_prompts import _compare_synthesize_result
    result = {
        "themes": [
            {
                "title": "测试主题",
                "summary": "摘要",
                "related_item_ids": ["abc123"],
                "significance": "意义",
                "counter_evidence": "有反面证据",
            }
        ],
        "connections": [{"from_theme": 0, "to_theme": 0, "relationship": "并列发展", "description": "关联"}],
        "overall_narrative": "全局叙事",
    }
    expected = {}
    score, issues = _compare_synthesize_result(result, expected)
    assert score < 6
    assert any("conclusion_type" in i for i in issues)


def test_compare_synthesize_result_wrong_conclusion_type():
    from hermes.pipeline.test_prompts import _compare_synthesize_result
    result = {
        "themes": [
            {
                "title": "测试主题",
                "summary": "摘要",
                "related_item_ids": ["abc123"],
                "significance": "意义",
                "counter_evidence": "有反面证据",
                "conclusion_type": "forecast",  # invalid!
            }
        ],
        "connections": [{"from_theme": 0, "to_theme": 0, "relationship": "并列发展", "description": "关联"}],
        "overall_narrative": "全局叙事",
    }
    expected = {}
    score, issues = _compare_synthesize_result(result, expected)
    assert score < 6
    assert any("conclusion_type" in i for i in issues)


def test_compare_synthesize_result_no_themes():
    from hermes.pipeline.test_prompts import _compare_synthesize_result
    result = {
        "themes": [],
        "connections": [],
        "overall_narrative": "empty",
    }
    expected = {}
    score, issues = _compare_synthesize_result(result, expected)
    assert score < 4
    assert any("themes" in i for i in issues)


def test_compare_synthesize_result_not_dict():
    from hermes.pipeline.test_prompts import _compare_synthesize_result
    score, issues = _compare_synthesize_result([], {})
    assert score == 0
    assert any("not a JSON object" in i for i in issues)


def test_compare_synthesize_result_missing_narrative():
    from hermes.pipeline.test_prompts import _compare_synthesize_result
    result = {
        "themes": [
            {
                "title": "T", "summary": "S", "related_item_ids": ["x"],
                "significance": "sig", "counter_evidence": "CE",
                "conclusion_type": "descriptive",
            }
        ],
        "connections": [],
        "overall_narrative": "",
    }
    expected = {"has_narrative": True}
    score, issues = _compare_synthesize_result(result, expected)
    assert any("overall_narrative" in i for i in issues)


def test_run_synthesize_tests_integration():
    """Integration test: run synthesize fixtures through prompt with mock LLM."""
    from hermes.pipeline.test_prompts import run_synthesize_tests

    mock_client = MagicMock()

    def mock_create(*args, **kwargs):
        msg = MagicMock()
        msg.choices = [MagicMock(message=MagicMock(
            content=json.dumps({
                "themes": [
                    {
                        "title": "测试主题",
                        "summary": "这是一个测试主题的摘要",
                        "related_item_ids": ["abc123def456"],
                        "significance": "测试意义",
                        "counter_evidence": "目前数据量有限，尚不能得出确定结论",
                        "conclusion_type": "evaluative",
                    }
                ],
                "connections": [
                    {"from_theme": 0, "to_theme": 0, "relationship": "因果关系", "description": "测试关联"}
                ],
                "overall_narrative": "测试全局叙事，描述整体趋势",
            })
        ))]
        return msg

    mock_client.chat.completions.create.side_effect = mock_create

    report = run_synthesize_tests(mock_client, limit=2, threshold=4)
    assert report["total"] == 2
    assert report["passed"] == 2


def test_format_synthesize_report_all_pass():
    from hermes.pipeline.test_prompts import format_synthesize_test_report
    report = {
        "passed": 3, "total": 3,
        "results": [
            {"fixture": "001", "score": 5, "issues": [], "theme_count": 2},
            {"fixture": "002", "score": 4, "issues": [], "theme_count": 1},
            {"fixture": "003", "score": 5, "issues": [], "theme_count": 3},
        ],
    }
    output = format_synthesize_test_report(report)
    assert "PASS" in output
    assert "safe to deploy" in output


def test_format_synthesize_report_with_failures():
    from hermes.pipeline.test_prompts import format_synthesize_test_report
    report = {
        "passed": 1, "total": 2,
        "results": [
            {"fixture": "001", "score": 5, "issues": [], "theme_count": 2},
            {"fixture": "002", "score": 2, "issues": ["counter_evidence: all themes must have non-empty counter_evidence"], "theme_count": 1},
        ],
    }
    output = format_synthesize_test_report(report)
    assert "FAIL" in output
    assert "below threshold" in output
