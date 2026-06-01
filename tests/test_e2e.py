def test_pipeline_smoke_imports():
    """Verify all pipeline stages can be imported."""
    from hermes.pipeline.run import run, status
    from hermes.pipeline.enrich import enrich_items
    from hermes.pipeline.dedup import dedup_items
    from hermes.pipeline.assess import assess_items
    from hermes.pipeline.synthesize import synthesize_items
    from hermes.pipeline.backtest import backtest_predictions
    assert True


def test_enrich_with_mock_clusterer():
    from hermes.embeddings import StreamingClusterer
    from hermes.pipeline.enrich import enrich_items

    clusterer = StreamingClusterer(distance_threshold=0.5)
    items = [
        {"id": "a", "title": "Test Article", "content": "This is test content about AI safety research."},
    ]
    result = enrich_items(items, clusterer)
    assert len(result) == 1
    assert "embedding" in result[0]
    assert len(result[0]["embedding"]) == 384
