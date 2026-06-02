import json
import re
from pathlib import Path

import numpy as np


def _load_prompt(name: str) -> str:
    path = Path(__file__).resolve().parent.parent / "prompts" / name
    return path.read_text()


_SYNTHESIZE_PROMPT = _load_prompt("synthesize.txt")


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
            if emb_i is not None and emb_j is not None:
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


def match_conclusion(
    candidate_embedding: list[float],
    candidate_confidence: float,
    existing_conclusions: list[dict],
    similarity_threshold: float = 0.85,
) -> tuple[str | None, str]:
    """Match a candidate conclusion against existing active conclusions.

    Returns (existing_conclusion_id, action) where action is one of:
      - "new": no match, create a new conclusion
      - "update": match found, confidence similar → update triggered_by
      - "version": match found, confidence changed significantly → new version
    """
    if not candidate_embedding or not existing_conclusions:
        return None, "new"

    best_id = None
    best_sim = -1.0
    best_confidence = 0.0

    for existing in existing_conclusions:
        emb = existing.get("embedding")
        if emb is None:
            continue
        sim = _cosine_similarity(candidate_embedding, emb)
        if sim > best_sim:
            best_sim = sim
            best_id = existing["id"]
            best_confidence = existing.get("confidence", 0.5)

    if best_id is None or best_sim < similarity_threshold:
        return None, "new"

    if abs(candidate_confidence - best_confidence) > 0.1:
        return best_id, "version"
    return best_id, "update"


def synthesize_items(
    items: list[dict],
    domains: list[str],
    client,
    min_score: float = 0.5,
    min_items: int = 3,
    feedback_context: str | None = None,
) -> dict | None:
    qualified = [
        i for i in items
        if max(i.get("exploit_score", 0), i.get("surprise_score", 0)) >= min_score
    ]
    qualified.sort(
        key=lambda i: i.get("exploit_score", 0) * 0.6 + i.get("surprise_score", 0) * 0.4,
        reverse=True,
    )
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

    prompt = _SYNTHESIZE_PROMPT.format(domain_list=domain_list)

    parts = [prompt]
    if feedback_context:
        parts.append(feedback_context)
    parts.append("---\n" + "\n---\n".join(summaries))
    user_msg = "\n\n".join(parts)

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
        parsed["_clusters"] = clusters
        return parsed
    except Exception:
        return None
