import tempfile
import os
import uuid
from hermes.db import Database


def test_insert_and_query_items():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = Database(path)
        db.insert_item(
            id="abc123",
            source="Test Blog",
            title="Hello World",
            url="https://example.com/1",
            content="Some content here",
            published_at="2026-05-22T09:00:00",
        )
        items = db.get_items_by_status("new")
        assert len(items) == 1
        assert items[0]["title"] == "Hello World"
        assert items[0]["source"] == "Test Blog"
    finally:
        os.unlink(path)


def test_update_item_status():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = Database(path)
        db.insert_item(
            id="x1", source="S", title="T", url="https://x.com",
            content="C", published_at=None,
        )
        db.update_item("x1", status="filtered", relevance_score=7, relevance_reason="relevant")
        items = db.get_items_by_status("filtered")
        assert len(items) == 1
        assert items[0]["relevance_score"] == 7
        assert items[0]["relevance_reason"] == "relevant"
    finally:
        os.unlink(path)


def test_get_items_by_status_excludes_others():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = Database(path)
        db.insert_item(id="a", source="S", title="A", url="https://a.com", content="C", published_at=None)
        db.insert_item(id="b", source="S", title="B", url="https://b.com", content="C", published_at=None)
        db.update_item("a", status="skipped")
        assert len(db.get_items_by_status("new")) == 1
        assert len(db.get_items_by_status("skipped")) == 1
    finally:
        os.unlink(path)


def test_run_log():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = Database(path)
        run_id = str(uuid.uuid4())
        db.log_run(run_id, "ingest", "ok", 10, 1500)
        db.log_run(run_id, "dedup", "ok", 8, 200)
        rows = db.get_run_logs(run_id)
        assert len(rows) == 2
        assert rows[0]["stage"] == "ingest"
        assert rows[0]["item_count"] == 10
    finally:
        os.unlink(path)


def test_feedback():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = Database(path)
        db.insert_feedback("item1", 4)
        db.insert_feedback("item1", 2)
        rows = db.get_all_feedback()
        assert len(rows) == 1
        assert rows[0]["rating"] == 2
    finally:
        os.unlink(path)


def test_get_item_count_by_cluster():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = Database(path)
        db.insert_item(id="a", source="S", title="A", url="https://a.com",
                       content="C", published_at=None)
        db.insert_item(id="b", source="S", title="B", url="https://b.com",
                       content="C", published_at=None)
        db.insert_item(id="c", source="S", title="C", url="https://c.com",
                       content="C", published_at=None)
        db.update_item("a", cluster_id="cl1")
        db.update_item("b", cluster_id="cl1")
        db.update_item("c", cluster_id="cl1")
        db.update_item("c", status="skipped")
        assert db.get_item_count_by_cluster("cl1") == 2
    finally:
        os.unlink(path)


def test_get_last_successful_run():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = Database(path)
        run1 = str(uuid.uuid4())
        run2 = str(uuid.uuid4())
        db.log_run(run1, "ingest", "ok", 10, 1000)
        db.log_run(run1, "write", "ok", 5, 500)
        db.log_run(run2, "ingest", "ok", 8, 800)
        assert db.get_last_successful_run() == run1
    finally:
        os.unlink(path)


def test_update_item_rejects_invalid_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = Database(path)
        db.insert_item(id="x", source="S", title="T", url="https://x.com",
                       content="C", published_at=None)
        import pytest
        with pytest.raises(ValueError, match="Invalid column"):
            db.update_item("x", nonexistent_field="value")
    finally:
        os.unlink(path)
