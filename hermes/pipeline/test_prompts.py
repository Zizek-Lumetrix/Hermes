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
        domain_choices = "|".join(domains)
        prompt_text = ASSESS_PROMPT.format(domains="、".join(domains), domain_choices=domain_choices)

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
