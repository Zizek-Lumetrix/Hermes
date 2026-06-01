import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def _load_prompt(name: str) -> str:
    path = Path(__file__).resolve().parent.parent / "prompts" / name
    return path.read_text()


ASSESS_PROMPT = _load_prompt("assess.txt")


def apply_rules(item: dict) -> bool:
    content = item.get("content", "")
    return len(content) >= 100


def assess_item(item: dict, domains: list[str], client) -> dict | None:
    domain_choices = "|".join(domains)
    prompt = ASSESS_PROMPT.format(domains="、".join(domains), domain_choices=domain_choices)

    title = item.get("title", "")
    content = item.get("content", "")[:3000]
    source = item.get("source", "")
    item_text = f"标题：{title}\n来源：{source}\n内容：{content}"

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"{prompt}\n\n{item_text}"}],
            temperature=0.2,
            max_tokens=1200,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```\w*\n?|```", "", raw)
        result = json.loads(raw)
    except (json.JSONDecodeError, KeyError, AttributeError):
        return None

    if not result.get("relevant", False):
        item["status"] = "skipped"
        return None

    item["analysis"] = json.dumps({
        "title_cn": result.get("title_cn", ""),
        "summary": result.get("summary", ""),
        "key_points": result.get("key_points", []),
        "implications": result.get("implications", ""),
        "confidence": result.get("confidence", "medium"),
    }, ensure_ascii=False)

    item["entities"] = json.dumps(result.get("entities", []), ensure_ascii=False)

    pred = result.get("prediction")
    item["prediction"] = json.dumps(pred, ensure_ascii=False) if pred else None

    score = float(result.get("exploit_score", 0))
    item["exploit_score"] = min(1.0, max(0.0, score / 10.0))
    domain = result.get("domain", "")
    item["domain"] = _match_domain(domain, domains)
    item["status"] = "assessed"
    return item


def _match_domain(raw: str, domains: list[str]) -> str:
    """Match LLM output to the nearest configured domain, or '' if no match."""
    if not raw or not raw.strip():
        return ""
    raw = raw.strip()
    if raw in domains:
        return raw
    # Try substring match: if the LLM output contains a known domain name
    for d in domains:
        if d in raw or raw in d:
            return d
    return ""


def assess_items(items: list[dict], domains: list[str], client, max_workers: int = 8) -> list[dict]:
    results = []
    futures_map: dict = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for item in items:
            if not apply_rules(item):
                item["status"] = "skipped"
                continue
            future = executor.submit(assess_item, item, domains, client)
            futures_map[future] = item

        for future in as_completed(futures_map):
            result = future.result()
            if result is not None:
                results.append(result)

    return results
