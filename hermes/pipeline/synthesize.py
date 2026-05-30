import json
import re

import numpy as np


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def density_peak_cluster(
    items: list[dict],
    distance_threshold: float = 0.5,
    min_cluster_size: int = 15,
) -> list[list[str]]:
    if len(items) < min_cluster_size:
        return [[item["id"] for item in items]]

    n = len(items)
    distances = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i + 1, n):
            emb_i = items[i].get("embedding")
            emb_j = items[j].get("embedding")
            if emb_i and emb_j:
                d = 1.0 - _cosine_similarity(emb_i, emb_j)
                distances[i][j] = d
                distances[j][i] = d

    density = np.zeros(n, dtype=np.float32)
    for i in range(n):
        density[i] = np.sum(distances[i] < distance_threshold)

    peaks = []
    for i in range(n):
        neighbors = [j for j in range(n) if j != i and distances[i][j] < distance_threshold]
        if all(density[i] > density[j] for j in neighbors):
            peaks.append(i)

    if not peaks:
        peaks = [int(np.argmax(density))]

    clusters: dict[int, list[str]] = {p: [] for p in peaks}
    for i in range(n):
        nearest = min(peaks, key=lambda p: distances[i][p])
        clusters[nearest].append(items[i]["id"])

    return list(clusters.values())


def synthesize_items(
    items: list[dict],
    domains: list[str],
    client,
    min_score: float = 0.5,
    min_items: int = 3,
) -> dict | None:
    qualified = [i for i in items if i.get("exploit_score", 0) >= min_score]
    qualified.sort(key=lambda i: i.get("exploit_score", 0), reverse=True)
    qualified = qualified[:60]

    if len(qualified) < min_items:
        return None

    clusters = density_peak_cluster(qualified, min_cluster_size=min_items)

    representatives = []
    for cl in clusters:
        rep = next((i for i in qualified if i["id"] in cl), None)
        if rep:
            representatives.append(rep)

    domain_list = "、".join(domains)

    summaries = []
    for item in representatives:
        try:
            analysis = json.loads(item.get("analysis", "{}"))
        except (json.JSONDecodeError, TypeError):
            analysis = {}
        title = analysis.get("title_cn", item.get("title", "Untitled"))
        summary = analysis.get("summary", "")[:200]
        source = item.get("source", "Unknown")
        short_id = item["id"][:12]
        summaries.append(
            f"[{short_id}] {title} (来源:{source})\n{summary}"
        )

    prompt = (
        f"你是一个情报分析专家，关注领域：{domain_list}。\n\n"
        f"以下是通过向量聚类自动发现的内容群组。请解释这些群组为什么存在："
        f"它们代表什么主题？条目之间有什么逻辑关联？\n\n"
        f"输出严格 JSON 格式（不含代码块标记）：\n"
        f'{{"themes": [{{"title": "<主题名称>", "summary": "<100字主题概述>", '
        f'"related_item_ids": ["<条目ID前缀>"], "significance": "<对该领域的意义>"}}], '
        f'"connections": [{{"from_theme": 0, "to_theme": 1, '
        f'"relationship": "因果关系|并列发展|对立矛盾|支撑佐证", '
        f'"description": "<一句话关联描述>"}}], '
        f'"overall_narrative": "<200字全局脉络>"}}\n\n'
        f"要求：themes 至少1个，每个至少关联1条条目。每条条目只归属一个主题。"
    )

    user_msg = prompt + "\n\n---\n" + "\n---\n".join(summaries)

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": user_msg}],
            temperature=0.3,
            max_tokens=4000,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```\w*\n?|```", "", raw)
        parsed = json.loads(raw)
        if not all(k in parsed for k in ("themes", "connections", "overall_narrative")):
            return None
        if not isinstance(parsed["themes"], list) or len(parsed["themes"]) == 0:
            return None
        return parsed
    except Exception:
        return None
