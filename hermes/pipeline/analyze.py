import json
import re


def _build_critique_prompt(domains: list[str]) -> str:
    domain_list = "、".join(domains)
    return f"""你是一个情报分析专家，关注领域：{domain_list}。

请对以下内容进行批判性分析：
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


def _build_extraction_prompt() -> str:
    return """请从以下内容中提取结构化信息。

输出严格 JSON 格式（不含代码块标记）：
{{
    "entities": [{{"name": "<实体名>", "type": "PERSON|ORG|CONCEPT|PRODUCT|EVENT|LOCATION", "mention_positions": [0, 1]}}],
    "prediction": {{"statement": "<可验证的预测>", "deadline": "YYYY-MM-DD", "outcome_var": "<可观测的结果变量>"}} 或 null
}}

要求：
- entities 只提取原文明确提及的实体，不要推断
- prediction 只提取有明确时间线和可验证结果的预测，否则为 null
- deadline 必须是具体的日期或可推断的日期"""


def analyze_items(
    items: list[dict],
    domains: list[str],
    client,
) -> list[dict]:
    critique_prompt = _build_critique_prompt(domains)
    extraction_prompt = _build_extraction_prompt()

    results = []
    for item in items:
        title = item.get("title", "")
        content = item.get("content", "")[:3000]
        source = item.get("source", "")
        item_text = f"标题：{title}\n来源：{source}\n内容：{content}"

        # Call 1: Critical analysis (t=0.3)
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": f"{critique_prompt}\n\n{item_text}"}],
                temperature=0.3,
                max_tokens=800,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```\w*\n?|```", "", raw)
            analysis = json.loads(raw)
            required = {"title_cn", "summary", "key_points", "implications", "confidence"}
            if not all(k in analysis for k in required):
                continue
        except Exception:
            continue

        # Call 2: Structure extraction (t=0.1)
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": f"{extraction_prompt}\n\n{item_text}"}],
                temperature=0.1,
                max_tokens=400,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```\w*\n?|```", "", raw)
            extracted = json.loads(raw)
            entities = extracted.get("entities", [])
            prediction = extracted.get("prediction")
        except Exception:
            entities = []
            prediction = None

        item["analysis"] = json.dumps(analysis, ensure_ascii=False)
        item["entities"] = json.dumps(entities, ensure_ascii=False)
        item["prediction"] = json.dumps(prediction, ensure_ascii=False) if prediction else None
        item["status"] = "analyzed"
        results.append(item)

    return results
