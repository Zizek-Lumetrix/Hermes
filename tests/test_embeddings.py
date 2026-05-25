import tempfile
import os
from pathlib import Path
from hermes.embeddings import EmbeddingIndex


def test_build_and_query_index():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "note1.md").write_text(
            "Machine learning fundamentals and neural network architectures"
        )
        (Path(tmpdir) / "note2.md").write_text(
            "Recipe for chocolate chip cookies with butter and sugar"
        )
        (Path(tmpdir) / "note3.md").write_text(
            "Deep learning with transformers and attention mechanisms"
        )

        index = EmbeddingIndex()
        index.build(tmpdir)

        assert len(index.paths) == 3

        query = "AI transformer models for NLP tasks"
        results = index.query(query, top_k=2)

        assert len(results) == 2
        # note3 should be most relevant (transformers + attention)
        assert "note3.md" in results[0][0]
        # note1 should be second (ML + neural networks)
        assert "note1.md" in results[1][0]


def test_empty_vault():
    with tempfile.TemporaryDirectory() as tmpdir:
        index = EmbeddingIndex()
        index.build(tmpdir)
        assert len(index.paths) == 0
        results = index.query("anything")
        assert results == []


def test_skip_non_markdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "readme.md").write_text("hello world")
        (Path(tmpdir) / "image.png").write_text("fake png")
        (Path(tmpdir) / "subdir").mkdir()
        (Path(tmpdir) / "subdir" / "deep.md").write_text("deep note content")

        index = EmbeddingIndex()
        index.build(tmpdir)

        assert len(index.paths) == 2
