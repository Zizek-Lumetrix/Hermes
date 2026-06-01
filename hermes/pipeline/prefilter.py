import json
import re


def apply_rules(item: dict, domains: list[str]) -> bool:
    content = item.get("content", "")
    if len(content) < 200:
        return False
    return True


def prefilter_items(
    items: list[dict],
    domains: list[str],
    client,
) -> list[dict]:
    domain_list = "、".join(domains)

    results = []
    for item in items:
        if not apply_rules(item, domains):
            item["status"] = "skipped"
            continue

        title = item.get("title", "")
        content_preview = item.get("content", "")[:300]
        user_msg = (
            f"关注领域：{domain_list}\n\n"
            f"标题：{title}\n"
            f"来源：{item.get('source', '')}\n"
            f"内容摘要：{content_preview}\n\n"
            f"这个条目是否与关注领域相关？输出JSON：{{\"continue\": 0或1}}"
        )

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.1,
                max_tokens=50,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```\w*\n?|```", "", raw)
            parsed = json.loads(raw)
            cont = int(parsed.get("continue", 0))
        except (json.JSONDecodeError, ValueError, KeyError, AttributeError):
            cont = 0

        if cont == 1:
            item["status"] = "prefiltered"
            results.append(item)
        else:
            item["status"] = "skipped"

    return results
