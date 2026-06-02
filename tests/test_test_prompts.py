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


# -- Synthesize test runner tests (split Stage 1 + Stage 2) --

def test_load_synthesize_fixtures():
    from hermes.pipeline.test_prompts import load_synthesize_fixtures
    fixtures = load_synthesize_fixtures()
    assert len(fixtures) == 4


def test_load_synthesize_fixtures_with_limit():
    from hermes.pipeline.test_prompts import load_synthesize_fixtures
    fixtures = load_synthesize_fixtures(limit=2)
    assert len(fixtures) == 2


def test_compare_theme_result_perfect():
    from hermes.pipeline.test_prompts import _compare_theme_result
    result = {
        "title": "AI编程工具竞争加剧",
        "conclusion_type": "evaluative",
        "summary": "多家公司推出AI编程工具",
        "significance": "改变软件开发范式",
        "counter_evidence": "目前所有工具都在演示阶段，实际部署数据有限",
        "related_item_ids": ["abc123def456"],
    }
    expected = {"expected_type": "evaluative"}
    score, issues = _compare_theme_result(result, expected)
    assert score == 4
    assert issues == []


def test_compare_theme_result_wrong_type():
    from hermes.pipeline.test_prompts import _compare_theme_result
    result = {
        "title": "测试主题",
        "conclusion_type": "descriptive",
        "summary": "摘要",
        "significance": "意义",
        "counter_evidence": "反面证据",
    }
    expected = {"expected_type": "predictive"}
    score, issues = _compare_theme_result(result, expected)
    assert score == 3
    assert any("conclusion_type" in i for i in issues)


def test_compare_theme_result_invalid_type():
    from hermes.pipeline.test_prompts import _compare_theme_result
    result = {
        "title": "测试主题",
        "conclusion_type": "forecast",
        "summary": "摘要",
        "significance": "意义",
        "counter_evidence": "反面证据",
    }
    expected = {}
    score, issues = _compare_theme_result(result, expected)
    assert score < 4
    assert any("conclusion_type" in i for i in issues)


def test_compare_theme_result_missing_type():
    from hermes.pipeline.test_prompts import _compare_theme_result
    result = {
        "title": "测试主题",
        "summary": "摘要",
        "significance": "意义",
        "counter_evidence": "反面证据",
    }
    expected = {}
    score, issues = _compare_theme_result(result, expected)
    assert score < 4
    assert any("conclusion_type" in i for i in issues)


def test_compare_theme_result_missing_counter_evidence():
    from hermes.pipeline.test_prompts import _compare_theme_result
    result = {
        "title": "测试主题",
        "conclusion_type": "descriptive",
        "summary": "摘要",
        "significance": "意义",
        "counter_evidence": "",
    }
    expected = {}
    score, issues = _compare_theme_result(result, expected)
    assert any("counter_evidence" in i for i in issues)


def test_compare_theme_result_not_dict():
    from hermes.pipeline.test_prompts import _compare_theme_result
    score, issues = _compare_theme_result([], {})
    assert score == 0
    assert any("not a JSON object" in i for i in issues)


def test_compare_cross_result_perfect():
    from hermes.pipeline.test_prompts import _compare_cross_result
    result = {
        "connections": [
            {"from_theme": 0, "to_theme": 1, "relationship": "因果关系", "description": "竞争驱动创新"}
        ],
        "overall_narrative": "AI编程工具市场正在快速演变",
    }
    expected = {"has_connections": True, "has_narrative": True}
    score, issues = _compare_cross_result(result, expected)
    assert score == 2
    assert issues == []


def test_compare_cross_result_no_connections():
    from hermes.pipeline.test_prompts import _compare_cross_result
    result = {
        "connections": [],
        "overall_narrative": "some narrative",
    }
    expected = {"has_connections": True}
    score, issues = _compare_cross_result(result, expected)
    assert any("connections" in i for i in issues)


def test_compare_cross_result_no_narrative():
    from hermes.pipeline.test_prompts import _compare_cross_result
    result = {
        "connections": [{"from_theme": 0, "to_theme": 0, "relationship": "支撑佐证", "description": "x"}],
        "overall_narrative": "",
    }
    expected = {"has_narrative": True}
    score, issues = _compare_cross_result(result, expected)
    assert any("overall_narrative" in i for i in issues)


def test_compare_cross_result_not_dict():
    from hermes.pipeline.test_prompts import _compare_cross_result
    score, issues = _compare_cross_result("not json", {})
    assert score == 0
    assert any("not a JSON object" in i for i in issues)


def test_run_synthesize_tests_integration():
    """Integration test: run split synthesize tests with mock LLM.

    The mock returns different responses for Stage 1 (theme extraction) and
    Stage 2 (cross synthesis) by inspecting the prompt content.
    """
    from hermes.pipeline.test_prompts import run_synthesize_tests

    mock_client = MagicMock()

    call_count = [0]

    def mock_create(*args, **kwargs):
        call_count[0] += 1
        msg = MagicMock()
        if call_count[0] % 2 == 1:
            # Stage 1: theme extraction
            content = json.dumps({
                "title": "测试主题",
                "conclusion_type": "evaluative",
                "summary": "这是一个测试主题的摘要",
                "significance": "测试意义",
                "counter_evidence": "目前数据量有限，尚不能得出确定结论",
                "related_item_ids": ["abc123def456"],
            })
        else:
            # Stage 2: cross synthesis
            content = json.dumps({
                "connections": [
                    {"from_theme": 0, "to_theme": 0, "relationship": "因果关系", "description": "测试关联"}
                ],
                "overall_narrative": "测试全局叙事，描述整体趋势",
            })
        msg.choices = [MagicMock(message=MagicMock(content=content))]
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
            {"fixture": "001", "score": 5, "theme_score": 3, "cross_score": 2,
             "issues": [], "theme_count": 1, "conclusion_type": "evaluative",
             "has_counter_evidence": True},
            {"fixture": "002", "score": 4, "theme_score": 2, "cross_score": 2,
             "issues": [], "theme_count": 1, "conclusion_type": "predictive",
             "has_counter_evidence": True},
            {"fixture": "003", "score": 6, "theme_score": 4, "cross_score": 2,
             "issues": [], "theme_count": 1, "conclusion_type": "descriptive",
             "has_counter_evidence": True},
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
            {"fixture": "001", "score": 5, "theme_score": 3, "cross_score": 2,
             "issues": [], "theme_count": 1, "conclusion_type": "evaluative",
             "has_counter_evidence": True},
            {"fixture": "002", "score": 2, "theme_score": 1, "cross_score": 1,
             "issues": ["[S1] counter_evidence: must be non-empty"], "theme_count": 1,
             "conclusion_type": "?", "has_counter_evidence": False},
        ],
    }
    output = format_synthesize_test_report(report)
    assert "FAIL" in output
    assert "below threshold" in output
