import json
import os
import uuid

import pytest

from hermes.db import Database


TEST_DSN = os.environ.get(
    "HERMES_TEST_DB", "postgresql:///hermes_test"
)

_TABLES = [
    "conclusion_versions",
    "conclusions",
    "predictions",
    "run_log",
    "items",
    "_migrations",
]


def _clean_tables(db: Database) -> None:
    try:
        db.conn.rollback()
    except Exception:
        pass
    for t in _TABLES:
        db.execute(f"TRUNCATE TABLE {t} CASCADE")
    db.conn.commit()


@pytest.fixture
def db():
    database = Database(TEST_DSN)
    _clean_tables(database)
    yield database
    _clean_tables(database)
    database.conn.close()


# ------------------------------------------------------------------
# Items
# ------------------------------------------------------------------

class TestItems:
    def test_insert_and_get_item(self, db: Database):
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

    def test_update_item_status(self, db: Database):
        db.insert_item(
            id="x1", source="S", title="T",
            url="https://x.com", content="C",
        )
        db.update_item("x1", status="filtered", exploit_score=7.5)
        items = db.get_items_by_status("filtered")
        assert len(items) == 1
        assert items[0]["exploit_score"] == 7.5

    def test_update_item_embedding(self, db: Database):
        db.insert_item(
            id="e1", source="S", title="T",
            url="https://e.com", content="C",
        )
        emb = [0.1] * 384
        db.update_item("e1", embedding=emb)
        # Inspect the raw text representation to verify storage
        row = db._query(
            "SELECT embedding::text AS emb FROM items WHERE id = %s", ("e1",)
        )[0]
        stored = json.loads(row["emb"])
        assert len(stored) == 384
        assert abs(stored[0] - 0.1) < 0.001

        # Also verify via get_items_by_status round-trip
        items = db.get_items_by_status("new")
        e = items[0]["embedding"]
        # pgvector returns a Vector (list-like) object
        assert e is not None

    def test_get_items_by_status_excludes_others(self, db: Database):
        db.insert_item(
            id="a", source="S", title="A",
            url="https://a.com", content="C",
        )
        db.insert_item(
            id="b", source="S", title="B",
            url="https://b.com", content="C",
        )
        db.update_item("a", status="skipped")
        assert len(db.get_items_by_status("new")) == 1
        assert len(db.get_items_by_status("skipped")) == 1

    def test_get_existing_urls(self, db: Database):
        db.insert_item(
            id="u1", source="S1", title="T1",
            url="https://a.com", content="C",
        )
        db.insert_item(
            id="u2", source="S2", title="T2",
            url="https://b.com", content="C",
        )
        urls = db.get_existing_urls()
        assert urls == {"https://a.com", "https://b.com"}

    def test_get_items_for_enrich(self, db: Database):
        db.insert_item(
            id="e1", source="S", title="T1",
            url="https://x.com", content="C",
        )
        db.insert_item(
            id="e2", source="S", title="T2",
            url="https://y.com", content="C",
        )
        db.update_item("e2", status="filtered")
        items = db.get_items_for_enrich()
        assert len(items) == 1
        assert items[0]["id"] == "e1"


# ------------------------------------------------------------------
# Run Log
# ------------------------------------------------------------------

class TestRunLog:
    def test_run_log(self, db: Database):
        run_id = str(uuid.uuid4())
        db.log_run(run_id, "ingest", "ok", 10, 1500)
        db.log_run(run_id, "dedup", "ok", 8, 200)
        rows = db.get_run_logs(run_id)
        assert len(rows) == 2
        assert rows[0]["stage"] == "ingest"
        assert rows[0]["item_count"] == 10

    def test_get_last_successful_run(self, db: Database):
        run1 = str(uuid.uuid4())
        run2 = str(uuid.uuid4())
        db.log_run(run1, "ingest", "ok", 10, 1000)
        db.log_run(run1, "backtest", "ok", 5, 500)
        db.log_run(run2, "ingest", "ok", 8, 800)
        assert db.get_last_successful_run() == run1


# ------------------------------------------------------------------
# Conclusions
# ------------------------------------------------------------------

class TestConclusions:
    def test_upsert_conclusion(self, db: Database):
        cid = str(uuid.uuid4())
        emb = [0.5] * 384
        db.upsert_conclusion(
            cid, "AI will transform X", "tech", 0.8, emb,
        )
        c = db.get_conclusion(cid)
        assert c is not None
        assert c["statement"] == "AI will transform X"
        assert c["domain"] == "tech"
        assert c["confidence"] == 0.8

        versions = db.get_conclusion_versions(cid)
        assert len(versions) == 1
        assert versions[0]["version"] == 1

    def test_update_conclusion_creates_new_version(self, db: Database):
        cid = str(uuid.uuid4())
        emb = [0.5] * 384
        db.upsert_conclusion(
            cid, "Original statement", "tech", 0.8, emb,
        )
        db.upsert_conclusion(
            cid, "Updated statement", "tech", 0.9, emb,
            change_description="Refined understanding",
        )
        c = db.get_conclusion(cid)
        assert c["statement"] == "Updated statement"
        assert c["confidence"] == 0.9

        versions = db.get_conclusion_versions(cid)
        assert len(versions) == 2
        assert versions[0]["version"] == 1
        assert versions[0]["statement"] == "Original statement"
        assert versions[1]["version"] == 2
        assert versions[1]["statement"] == "Updated statement"

    def test_get_all_conclusions(self, db: Database):
        emb = [0.5] * 384
        cid1 = str(uuid.uuid4())
        cid2 = str(uuid.uuid4())
        db.upsert_conclusion(cid1, "Conclusion 1", "tech", 0.8, emb)
        db.upsert_conclusion(cid2, "Conclusion 2", "science", 0.6, emb)
        conclusions = db.get_all_conclusions()
        assert len(conclusions) == 2
        statements = {c["statement"] for c in conclusions}
        assert statements == {"Conclusion 1", "Conclusion 2"}

    def test_confirm_conclusion(self, db: Database):
        cid = str(uuid.uuid4())
        db.upsert_conclusion(
            cid, "Test conclusion", "tech", 0.8, [0.5] * 384,
        )
        db.confirm_conclusion(cid, "confirmed")
        c = db.get_conclusion(cid)
        assert c["user_confirmation"] == "confirmed"

        db.confirm_conclusion(cid, "challenged")
        c = db.get_conclusion(cid)
        assert c["user_confirmation"] == "challenged"

    def test_confirm_conclusion_rejects_invalid(self, db: Database):
        cid = str(uuid.uuid4())
        db.upsert_conclusion(
            cid, "Test", "tech", 0.8, [0.5] * 384,
        )
        with pytest.raises(ValueError, match="confirmation must be"):
            db.confirm_conclusion(cid, "invalid")


# ------------------------------------------------------------------
# Predictions
# ------------------------------------------------------------------

class TestPredictions:
    def test_insert_and_query_predictions(self, db: Database):
        item_id = "pred-item"
        db.insert_item(
            id=item_id, source="S", title="T",
            url="https://p.com", content="C",
        )
        pid = db.insert_prediction(
            item_id, "Stock will rise", "2025-01-01",
        )
        pending = db.get_pending_predictions()
        assert len(pending) == 1
        assert pending[0]["id"] == pid

    def test_update_prediction_result(self, db: Database):
        item_id = "pred-item2"
        db.insert_item(
            id=item_id, source="S", title="T",
            url="https://p2.com", content="C",
        )
        pid = db.insert_prediction(
            item_id, "Will happen", "2025-01-01",
        )
        db.update_prediction_result(pid, "correct", "Event confirmed")
        pending = db.get_pending_predictions()
        assert len(pending) == 0

        all_preds = db.get_all_predictions()
        assert len(all_preds) == 1
        assert all_preds[0]["backtest_result"] == "correct"
        assert all_preds[0]["backtest_reason"] == "Event confirmed"

    def test_get_all_predictions_filter(self, db: Database):
        item_id = "pred-item3"
        db.insert_item(
            id=item_id, source="S", title="T",
            url="https://p3.com", content="C",
        )
        pid1 = db.insert_prediction(
            item_id, "Pred A", "2025-01-01",
        )
        pid2 = db.insert_prediction(
            item_id, "Pred B", "2025-06-01",
        )
        db.update_prediction_result(pid1, "correct")

        assert len(db.get_all_predictions("pending")) == 1
        assert len(db.get_all_predictions("verified")) == 1
        assert len(db.get_all_predictions("all")) == 2
