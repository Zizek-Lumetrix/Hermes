import json
import re


def backtest_predictions(
    pending: list[dict],
    client,
) -> list[dict]:
    results = []

    for pred in pending:
        user_msg = (
            f"请验证以下预测是否成真。基于你的训练知识判断。\n\n"
            f"预测陈述：{pred['statement']}\n"
            f"截止日期：{pred['deadline']}\n"
            f"可观测结果变量：{pred.get('outcome_var', '')}\n\n"
            f'输出JSON：{{"result": "correct|incorrect|partially_correct|unverifiable", '
            f'"reason": "<一句话说明判断依据>"}}'
        )

        result = "unverifiable"
        reason = ""

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.1,
                max_tokens=200,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```\w*\n?|```", "", raw)
            parsed = json.loads(raw)
            result = parsed.get("result", "unverifiable")
            reason = parsed.get("reason", "")
        except Exception:
            pass

        results.append({
            "id": pred["id"],
            "item_id": pred.get("item_id", ""),
            "result": result,
            "reason": reason,
        })

    return results
