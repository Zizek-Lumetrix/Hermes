"""Prompt regression testing: run current prompts against annotated fixtures.

Usage: hermes test-prompts [-n N] [--threshold 4]
"""

import json
import re
from pathlib import Path


FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"


def load_fixtures(limit: int | None = None) -> list[dict]:
    fixtures = []
    for f in sorted(FIXTURES_DIR.glob("*.json")):
        fixture = json.loads(f.read_text())
        fixture["_id"] = f.stem
        fixtures.append(fixture)
        if limit and len(fixtures) >= limit:
            break
    return fixtures


def _compare_result(result: dict, expected: dict) -> tuple[int, list[str]]:
    """Compare an LLM result against expected values.

    Returns (score 0-5, list of issues).
    """
    score = 0
    issues = []

    rel_ok = result.get("relevant") == expected.get("relevant")
    if rel_ok:
        score += 1
    else:
        issues.append(f"relevant: expected {expected.get('relevant')}, got {result.get('relevant')}")

    if result.get("domain") == expected.get("domain"):
        score += 1
    else:
        issues.append(f"domain: expected {expected.get('domain')}, got {result.get('domain')}")

    conf = result.get("confidence", "")
    if conf in ("high", "medium", "low"):
        score += 1
    else:
        issues.append(f"confidence: invalid value '{conf}'")

    score_ok = (0 <= result.get("exploit_score", -1) <= 10)
    if score_ok:
        score += 1
    else:
        issues.append(f"exploit_score: expected 0-10, got {result.get('exploit_score')}")

    required = {"title_cn", "summary", "key_points", "implications"}
    if required.issubset(result.keys()):
        score += 1
    else:
        missing = required - result.keys()
        issues.append(f"missing fields: {missing}")

    return score, issues


def _parse_response(raw: str) -> dict | None:
    """Parse LLM response into dict."""
    try:
        raw = re.sub(r"```\w*\n?|```", "", raw.strip())
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def run_prompt_tests(client, domains: list[str] | None = None,
                    limit: int | None = None, threshold: int = 4) -> dict:
    """Run prompt regression tests against all fixtures."""
    if domains is None:
        domains = ["AI编程工具", "大模型安全", "中东局势", "能源安全", "地缘政治"]

    from hermes.pipeline.assess import ASSESS_PROMPT

    fixtures = load_fixtures(limit=limit)
    if not fixtures:
        print("No fixtures found.")
        return {"passed": 0, "total": 0, "results": []}

    results = []
    for fix in fixtures:
        prompt_text = ASSESS_PROMPT.format(domains="、".join(domains))

        item_text = f"标题：{fix['title']}\n来源：{fix['source']}\n内容：{fix['content'][:3000]}"
        user_msg = f"{prompt_text}\n\n{item_text}"

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.2,
                max_tokens=1200,
            )
            raw = response.choices[0].message.content.strip()
            result = _parse_response(raw)
        except Exception as e:
            result = None

        if result is None:
            results.append({
                "fixture": fix["_id"],
                "title": fix["title"],
                "score": 0,
                "issues": ["LLM call failed or JSON parse error"],
            })
            continue

        expected = fix.get("expected", {})
        score, issues = _compare_result(result, expected)
        results.append({
            "fixture": fix["_id"],
            "title": fix["title"],
            "score": score,
            "issues": issues,
            "domain": result.get("domain", ""),
            "confidence": result.get("confidence", ""),
            "exploit_score": result.get("exploit_score", 0),
        })

    passed = sum(1 for r in results if r["score"] >= threshold)
    return {"passed": passed, "total": len(results), "results": results}


def format_prompt_test_report(report: dict) -> str:
    lines = []
    lines.append(f"\n{'=' * 60}")
    lines.append("PROMPT REGRESSION TEST REPORT")
    lines.append(f"{'=' * 60}")
    lines.append(f"Passed: {report['passed']}/{report['total']}")

    for r in report["results"]:
        status = "PASS" if r["score"] >= 4 else "FAIL"
        bar = "=" * r["score"] + "-" * (5 - r["score"])
        lines.append(f"\n  [{status}] {r['fixture']}")
        lines.append(f"  Score: [{bar}] {r['score']}/5")
        lines.append(f"  Domain: {r.get('domain', '?')} | Confidence: {r.get('confidence', '?')} | Exploit: {r.get('exploit_score', '?')}")
        if r["issues"]:
            for issue in r["issues"]:
                lines.append(f"  -> {issue}")

    if report["passed"] < report["total"]:
        lines.append(f"\n!!! {report['total'] - report['passed']} fixture(s) below threshold. Review prompt changes.")
    else:
        lines.append(f"\nAll fixtures passed. Prompt changes are safe to deploy.")

    return "\n".join(lines)


# -- Synthesize prompt regression tests --

SYNTHESIZE_FIXTURES_DIR = FIXTURES_DIR / "synthesize"


def load_synthesize_fixtures(limit: int | None = None) -> list[dict]:
    fixtures = []
    if not SYNTHESIZE_FIXTURES_DIR.is_dir():
        return fixtures
    for f in sorted(SYNTHESIZE_FIXTURES_DIR.glob("*.json")):
        fixture = json.loads(f.read_text())
        fixture["_id"] = f.stem
        fixtures.append(fixture)
        if limit and len(fixtures) >= limit:
            break
    return fixtures


def _compare_synthesize_result(result: dict, expected: dict) -> tuple[int, list[str]]:
    """Compare a synthesize LLM result against expected structure.

    Returns (score 0-6, list of issues).
    """

    VALID_TYPES = {"predictive", "evaluative", "descriptive"}

    score = 0
    issues = []

    if not isinstance(result, dict):
        return 0, ["result is not a JSON object"]

    themes = result.get("themes", [])
    if isinstance(themes, list) and len(themes) > 0:
        score += 1
    else:
        issues.append("themes: must be a non-empty array")

    min_themes = expected.get("min_themes", 1)
    if isinstance(themes, list) and len(themes) >= min_themes:
        score += 1
    else:
        issues.append(f"theme_count: expected at least {min_themes}, got {len(themes) if isinstance(themes, list) else 0}")

    if expected.get("has_counter_evidence", True):
        all_have_counter = all(
            isinstance(t.get("counter_evidence"), str) and len(t.get("counter_evidence", "")) > 0
            for t in (themes if isinstance(themes, list) else [])
        )
        if all_have_counter:
            score += 1
        else:
            issues.append("counter_evidence: all themes must have non-empty counter_evidence")

    if expected.get("has_conclusion_type", True):
        all_have_ctype = all(
            t.get("conclusion_type") in VALID_TYPES
            for t in (themes if isinstance(themes, list) else [])
        )
        if all_have_ctype:
            score += 1
        else:
            invalid = [
                f"{t.get('title', '?')}={t.get('conclusion_type', 'missing')}"
                for t in (themes if isinstance(themes, list) else [])
                if t.get("conclusion_type") not in VALID_TYPES
            ]
            issues.append(f"conclusion_type: all themes need valid type (predictive|evaluative|descriptive). Invalid: {invalid}")

    connections = result.get("connections", [])
    if expected.get("has_connections", True):
        if isinstance(connections, list) and len(connections) > 0:
            score += 1
        else:
            issues.append("connections: must be a non-empty array")

    narrative = result.get("overall_narrative", "")
    if expected.get("has_narrative", True):
        if isinstance(narrative, str) and len(narrative) > 0:
            score += 1
        else:
            issues.append("overall_narrative: must be a non-empty string")

    return score, issues


def run_synthesize_tests(client, limit: int | None = None, threshold: int = 4) -> dict:
    """Run synthesize prompt regression tests against fixtures."""
    from hermes.pipeline.synthesize import _SYNTHESIZE_PROMPT

    fixtures = load_synthesize_fixtures(limit=limit)
    if not fixtures:
        return {"passed": 0, "total": 0, "results": []}

    results = []
    for fix in fixtures:
        # Build user message the same way synthesize_items does
        summaries = []
        for item in fix["items"]:
            analysis = item.get("analysis", {})
            title = analysis.get("title_cn", item.get("title", "Untitled"))
            summary = analysis.get("summary", "")[:200]
            source = item.get("source", "Unknown")
            short_id = item["id"][:12]
            summaries.append(
                f"[{short_id}] {title} (来源:{source})\n{summary}"
            )

        prompt = _SYNTHESIZE_PROMPT.format(domain_list=fix["domain_list"])
        user_msg = prompt + "\n\n---\n" + "\n---\n".join(summaries)

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.3,
                max_tokens=4000,
            )
            raw = response.choices[0].message.content.strip()
            result = _parse_response(raw)
        except Exception:
            result = None

        if result is None:
            results.append({
                "fixture": fix["_id"],
                "score": 0,
                "issues": ["LLM call failed or JSON parse error"],
            })
            continue

        expected = fix.get("expected", {})
        score, issues = _compare_synthesize_result(result, expected)
        theme_count = len(result.get("themes", []))
        results.append({
            "fixture": fix["_id"],
            "score": score,
            "issues": issues,
            "theme_count": theme_count,
        })

    passed = sum(1 for r in results if r["score"] >= threshold)
    return {"passed": passed, "total": len(results), "results": results}


def format_synthesize_test_report(report: dict) -> str:
    lines = []
    lines.append(f"\n{'=' * 60}")
    lines.append("SYNTHESIZE PROMPT REGRESSION TEST REPORT")
    lines.append(f"{'=' * 60}")
    lines.append(f"Passed: {report['passed']}/{report['total']}")

    for r in report["results"]:
        status = "PASS" if r["score"] >= 4 else "FAIL"
        bar = "=" * r["score"] + "-" * (6 - r["score"])
        lines.append(f"\n  [{status}] {r['fixture']}")
        lines.append(f"  Score: [{bar}] {r['score']}/6")
        lines.append(f"  Themes: {r.get('theme_count', '?')}")
        if r["issues"]:
            for issue in r["issues"]:
                lines.append(f"  -> {issue}")

    if report["passed"] < report["total"]:
        lines.append(f"\n!!! {report['total'] - report['passed']} fixture(s) below threshold. Review prompt changes.")
    else:
        lines.append(f"\nAll fixtures passed. Prompt changes are safe to deploy.")

    return "\n".join(lines)
