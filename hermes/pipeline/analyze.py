import json
import re


def build_analyze_prompt(domains: list[str]) -> str:
    domain_list = "、".join(domains)
    return f"""你是一个情报分析专家，关注领域：{domain_list}。

请对以下内容进行批判性分析。注意：
- 识别信源偏见和未被验证的断言
- 与其他已知信息的矛盾之处
- 区分事实陈述与观点推断

输出严格 JSON 格式（不含代码块标记）：
{{
    "title_cn": "<中文标题>",
    "summary": "<200字批判性摘要>",
    "key_points": ["<要点1>", "<要点2>", "<要点3>"],
    "implications": "<对从业者的一两句话启示>",
    "confidence": "high|medium|low"
}}"""


def analyze_items(
    items: list[dict],
    domains: list[str],
    client,
) -> list[dict]:
    prompt_template = build_analyze_prompt(domains)

    for item in items:
        content = f"标题：{item['title']}\n来源：{item['source']}\n内容：{item['content'][:3000]}"
        user_msg = f"{prompt_template}\n\n{content}"

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.3,
                max_tokens=800,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```\w*\n?|```", "", raw)
            parsed = json.loads(raw)
        except (json.JSONDecodeError, Exception):
            item["status"] = "skipped"
            continue

        item["analysis"] = json.dumps(parsed, ensure_ascii=False)
        item["status"] = "analyzed"

    return items
