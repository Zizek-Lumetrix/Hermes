import json
from unittest.mock import MagicMock
from hermes.pipeline.synthesize import density_peak_cluster, synthesize_items, match_conclusion


def test_density_peak_clustering():
    items = [
        {"id": "a", "embedding": [0.9, 0.1]},
        {"id": "b", "embedding": [0.89, 0.11]},
        {"id": "c", "embedding": [0.1, 0.9]},
        {"id": "d", "embedding": [0.11, 0.89]},
    ]
    clusters = density_peak_cluster(items, distance_threshold=0.15, min_cluster_size=3)
    assert len(clusters) >= 1
    all_ids = [item_id for cl in clusters for item_id in cl]
    assert "a" in all_ids
    assert "c" in all_ids


def test_density_peak_below_min_returns_single_cluster():
    items = [
        {"id": "a", "embedding": [0.1, 0.2]},
        {"id": "b", "embedding": [0.8, 0.9]},
    ]
    clusters = density_peak_cluster(items, min_cluster_size=3)
    assert len(clusters) == 1
    assert len(clusters[0]) == 2
    assert "a" in clusters[0]
    assert "b" in clusters[0]


def test_synthesize_uses_llm_to_explain():
    items = [
        {"id": "a", "title": "AI Paper 1", "source": "ArXiv",
         "analysis": json.dumps({"title_cn": "AI论文1", "summary": "关于对齐的研究。"}),
         "exploit_score": 0.8, "embedding": [0.1] * 384},
        {"id": "b", "title": "AI Paper 2", "source": "ArXiv",
         "analysis": json.dumps({"title_cn": "AI论文2", "summary": "关于安全的研究。"}),
         "exploit_score": 0.7, "embedding": [0.11] * 384},
        {"id": "c", "title": "Oil News", "source": "Reuters",
         "analysis": json.dumps({"title_cn": "油价新闻", "summary": "原油价格上涨。"}),
         "exploit_score": 0.6, "embedding": [0.9] * 384},
    ]

    mock_client = MagicMock()

    def mock_create(*args, **kwargs):
        m = MagicMock()
        content = kwargs.get("messages", [{}])[0].get("content", "")
        # Stage 1: theme extraction (per-cluster call)
        if "以下是一组通过向量聚类发现的语义相关文章" in content:
            m.choices = [MagicMock(message=MagicMock(content=json.dumps({
                "title": "AI安全进展", "conclusion_type": "evaluative",
                "summary": "多项AI安全研究取得进展",
                "significance": "合规要求趋严",
                "counter_evidence": "当前研究样本量有限，结论可能不具普遍性",
                "related_item_ids": ["a", "b"],
            })))]
        else:
            # Stage 2: cross synthesis
            m.choices = [MagicMock(message=MagicMock(content=json.dumps({
                "connections": [],
                "overall_narrative": "AI安全领域持续活跃，能源市场波动。",
            })))]
        return m

    mock_client.chat.completions.create.side_effect = mock_create

    result = synthesize_items(items, ["AI安全", "能源"], mock_client)
    assert result is not None
    assert len(result["themes"]) == 1
    assert result["themes"][0]["title"] == "AI安全进展"


def test_synthesize_returns_none_for_few_items():
    items = [{"id": "x", "title": "Single item", "source": "Test",
              "analysis": "{}", "exploit_score": 0.5, "embedding": [0.1] * 384}]
    result = synthesize_items(items, ["AI"], MagicMock())
    assert result is None


def test_match_conclusion_no_existing_returns_new():
    result_id, action = match_conclusion([0.1] * 384, 0.6, [])
    assert result_id is None
    assert action == "new"


def test_match_conclusion_match_found_similar_confidence():
    existing = [{"id": "c1", "statement": "AI safety improving",
                 "confidence": 0.65, "embedding": [0.11] * 384}]
    result_id, action = match_conclusion([0.1] * 384, 0.6, existing)
    assert result_id == "c1"
    assert action == "update"


def test_match_conclusion_match_found_different_confidence():
    existing = [{"id": "c1", "statement": "AI safety improving",
                 "confidence": 0.4, "embedding": [0.11] * 384}]
    result_id, action = match_conclusion([0.1] * 384, 0.7, existing)
    assert result_id == "c1"
    assert action == "version"


def test_match_conclusion_no_match_below_threshold():
    # Use orthogonal-like embeddings to ensure low similarity
    existing = [{"id": "c1", "statement": "Oil prices rising",
                 "confidence": 0.5, "embedding": [1.0] * 192 + [-1.0] * 192}]
    result_id, action = match_conclusion([1.0] * 384, 0.6, existing)
    assert result_id is None
    assert action == "new"
