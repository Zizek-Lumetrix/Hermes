import json
import re


def backtest_predictions(
    pending: list[dict],
    client,
    confirmation_stats: dict | None = None,
) -> list[dict]:
    results = []

    feedback = ""
    if confirmation_stats and confirmation_stats.get("total", 0) > 0:
        confirmed_pct = confirmation_stats["confirmed"] / confirmation_stats["total"] * 100
        feedback = (
            f"\n参考：此前有 {confirmation_stats['total']} 条预测性结论经审核，"
            f"确认率为 {confirmed_pct:.0f}%。"
        )

    for pred in pending:
        user_msg = (
            f"请严格验证以下预测是否已经成真。使用你的训练知识进行判断。{feedback}\n\n"
            f"预测陈述：{pred['statement']}\n"
            f"截止日期：{pred['deadline']}\n"
            f"可观测变量：{pred.get('outcome_var', '') or '无'}\n\n"
            "判断标准：\n"
            "- correct: 有明确证据表明预测成真\n"
            "- incorrect: 有明确证据表明预测未发生或为假\n"
            "- partially_correct: 预测大致正确但细节有出入\n"
            "- unverifiable: 缺乏足够信息判断真伪\n\n"
            "输出JSON（不含代码块标记）：\n"
            '{"result": "correct|incorrect|partially_correct|unverifiable", '
            '"reason": "<50字说明关键证据或不可验证的原因>"}'
        )

        result = "unverifiable"
        reason = ""

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.1,
                max_tokens=300,
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
