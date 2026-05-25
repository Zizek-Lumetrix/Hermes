import json
import re


def build_filter_prompt(domains: list[str], feedback_notes: list[dict]) -> str:
    domain_list = "、".join(domains)
    prompt = f"""你是一个信息过滤器。用户关注以下领域：{domain_list}。

请对以下内容评分（0-10）：
- 10 = 直接核心相关，用户必须知道
- 5 = 有一定关联
- 0 = 完全无关

输出严格 JSON 格式，不包含任何其他文字：
{{"score": <整数0-10>, "reason": "<一句话理由，score<3时可为空>"}}"""

    if feedback_notes:
        low_rated = [f for f in feedback_notes if f.get("rating", 0) <= 2]
        high_rated = [f for f in feedback_notes if f.get("rating", 0) >= 4]
        if low_rated or high_rated:
            prompt += "\n\n用户偏好参考："
            if low_rated:
                prompt += f"\n- 用户对类似以下内容打过低分: {low_rated[:3]}"
            if high_rated:
                prompt += f"\n- 用户对类似以下内容打过高分: {high_rated[:3]}"

    return prompt


def filter_items(
    items: list[dict],
    domains: list[str],
    feedback: list[dict],
    client,
    threshold: int = 3,
) -> list[dict]:
    prompt_template = build_filter_prompt(domains, feedback)

    for item in items:
        content = f"标题：{item['title']}\n来源：{item['source']}\n内容：{item['content'][:1500]}"
        user_msg = f"{prompt_template}\n\n{content}"

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.1,
                max_tokens=100,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```\w*\n?|```", "", raw)
            parsed = json.loads(raw)
            score = int(parsed.get("score", 0))
            reason = parsed.get("reason", "")
        except (json.JSONDecodeError, ValueError, KeyError, AttributeError):
            score = 0
            reason = "parse error"

        item["relevance_score"] = score
        item["relevance_reason"] = reason
        item["status"] = "filtered" if score >= threshold else "skipped"

    return items
