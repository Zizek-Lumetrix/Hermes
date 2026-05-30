import numpy as np
from hermes.embeddings import StreamingClusterer


def test_first_item_creates_centroid():
    clusterer = StreamingClusterer(distance_threshold=0.5)
    embedding = [0.1] * 384
    cluster_id = clusterer.assign(embedding)
    assert cluster_id == 0
    assert len(clusterer.centroids) == 1


def test_similar_items_share_cluster():
    clusterer = StreamingClusterer(distance_threshold=0.5)
    emb1 = [0.5] * 384
    emb2 = [0.51] * 384
    c1 = clusterer.assign(emb1)
    c2 = clusterer.assign(emb2)
    assert c1 == 0
    assert c2 == 0
    assert len(clusterer.centroids) == 1


def test_dissimilar_items_create_new_cluster():
    clusterer = StreamingClusterer(distance_threshold=0.3)
    emb1 = [1.0] + [0.0] * 383
    emb2 = [0.0] * 192 + [1.0] + [0.0] * 191
    c1 = clusterer.assign(emb1)
    c2 = clusterer.assign(emb2)
    assert c1 == 0
    assert c2 == 1
    assert len(clusterer.centroids) == 2


def test_cold_start_seeds_centroids():
    clusterer = StreamingClusterer(distance_threshold=0.3)
    embeddings = [
        [1.0] + [0.0] * 383,
        [1.01] + [0.0] * 383,
        [0.0] * 192 + [1.0] + [0.0] * 191,
        [0.0] * 192 + [1.01] + [0.0] * 191,
    ]
    clusterer.cold_start(embeddings)
    assert len(clusterer.centroids) == 2
    c = clusterer.assign([1.02] + [0.0] * 383)
    assert c in (0, 1)


def test_centroids_are_normalized():
    clusterer = StreamingClusterer(distance_threshold=0.5)
    emb = [0.5] * 384
    clusterer.assign(emb)
    centroid = clusterer.centroids[0]
    norm = np.linalg.norm(centroid)
    assert abs(norm - 1.0) < 0.01


from hermes.pipeline.enrich import enrich_items


def test_enrich_adds_embedding_and_cluster():
    clusterer = StreamingClusterer(distance_threshold=0.5)
    items = [
        {"id": "a", "title": "AI Safety Paper", "content": "Research on AI alignment."},
        {"id": "b", "title": "Oil Prices Rise", "content": "Crude oil up 5%."},
    ]
    result = enrich_items(items, clusterer)
    assert len(result) == 2
    for item in result:
        assert "embedding" in item
        assert len(item["embedding"]) == 384
        assert isinstance(item["implicit_cluster"], int)
        assert item["status"] == "enriched"


def test_enrich_handles_empty_list():
    clusterer = StreamingClusterer()
    result = enrich_items([], clusterer)
    assert result == []
