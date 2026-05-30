import json
from unittest.mock import MagicMock


def test_pipeline_smoke_imports():
    """Verify all pipeline stages can be imported."""
    from hermes.pipeline.run import run, status
    from hermes.pipeline.enrich import enrich_items
    from hermes.pipeline.dedup import dedup_items
    from hermes.pipeline.prefilter import prefilter_items
    from hermes.pipeline.analyze import analyze_items
    from hermes.pipeline.postfilter import score_items
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


def test_prefilter_rules_reject_short():
    from hermes.pipeline.prefilter import apply_rules
    assert not apply_rules({"content": "short"}, ["AI"])


def test_prefilter_rules_accept_domain_match():
    from hermes.pipeline.prefilter import apply_rules
    item = {
        "title": "AI Safety Paper",
        "content": "Research on AI alignment. " * 10,
        "source": "ArXiv",
    }
    assert apply_rules(item, ["AI"])
