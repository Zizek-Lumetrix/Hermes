import json
import re


def score_items(
    items: list[dict],
    domains: list[str],
    client,
) -> list[dict]:
    domain_list = "、".join(domains)

    for item in items:
        title = item.get("title", "")
        content_preview = item.get("content", "")[:500]

        user_msg = (
            f"关注领域：{domain_list}\n\n"
            f"标题：{title}\n"
            f"来源：{item.get('source', '')}\n"
            f"内容：{content_preview}\n\n"
            f"评估此条目的可操作性/实用价值（exploitability）：0=纯理论无实用价值，10=直接可操作、有明确的行动启示。\n"
            f"输出JSON：{{\"exploit_score\": <整数0-10>}}"
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
            score = float(parsed.get("exploit_score", 0))
        except (json.JSONDecodeError, ValueError, KeyError, AttributeError):
            score = 0.0

        item["exploit_score"] = score / 10.0
        item["status"] = "scored"

    return items
