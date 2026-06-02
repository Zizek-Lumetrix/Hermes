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
    return len(content) >= 60


def assess_item(item: dict, domains: list[str], client) -> dict | None:
    prompt = ASSESS_PROMPT.format(domains="、".join(domains))

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
    domain = result.get("domain", "").strip()
    proposed = result.get("domain_proposed", "").strip()
    item["domain"] = domain if domain else ""
    item["domain_proposed"] = proposed if proposed else None
    item["status"] = "assessed"
    return item


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
