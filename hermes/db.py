import json
import uuid
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector


_ALLOWED_COLUMNS = frozenset({
    "source", "title", "url", "content", "published_at",
    "fingerprint", "cluster_id", "embedding", "implicit_cluster",
    "analysis", "entities", "prediction", "exploit_score", "surprise_score",
    "status", "domain", "domain_proposed", "category", "tags",
})

_VECTOR_COLUMNS = frozenset({"embedding"})
_JSONB_COLUMNS = frozenset({"analysis", "entities", "prediction"})
_ARRAY_COLUMNS = frozenset({"tags"})


def _find_migrations_dir() -> Path:
    """Locate the migrations directory relative to this package."""
    return Path(__file__).resolve().parent.parent / "migrations"


class Database:
    """PostgreSQL-backed database for Hermes v2.

    Uses psycopg2 directly with pgvector support.
    On init, runs any pending SQL migrations from the ``migrations/`` directory.
    """

    def __init__(self, dsn: str):
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = False
        register_vector(self.conn)
        self._run_migrations()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_migrations(self) -> None:
        """Execute all pending migration ``.sql`` files in sorted order."""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT now()
                )
            """)
        self.conn.commit()

        migrations_dir = _find_migrations_dir()
        if not migrations_dir.exists():
            return

        applied = {r["name"] for r in self._query("SELECT name FROM _migrations")}
        for f in sorted(migrations_dir.glob("*.sql")):
            if f.name not in applied:
                sql = f.read_text()
                try:
                    with self.conn.cursor() as cur:
                        cur.execute(sql)
                    self.conn.commit()
                    self.execute(
                        "INSERT INTO _migrations (name) VALUES (%s)", (f.name,)
                    )
                except Exception:
                    self.conn.rollback()
                    raise

    def _query(self, sql: str, params: tuple | None = None) -> list[dict]:
        """Execute a SELECT and return results as a list of dicts."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def execute(self, sql: str, params: tuple | None = None) -> None:
        """Execute a mutation statement (does not commit)."""
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def _commit(self) -> None:
        """Commit and restore clean state on error."""
        try:
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    def insert_item(
        self,
        id: str,
        source: str,
        title: str,
        url: str,
        content: str,
        published_at: str | None = None,
    ) -> None:
        self.execute(
            "INSERT INTO items (id, source, title, url, content, published_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (id, source, title, url, content, published_at),
        )
        self._commit()

    def update_item(self, id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        for k in kwargs:
            if k not in _ALLOWED_COLUMNS:
                raise ValueError(f"Invalid column: {k}")

        set_clauses: list[str] = []
        values: list[Any] = []
        for k, v in kwargs.items():
            if k in _VECTOR_COLUMNS:
                set_clauses.append(f"{k} = %s::vector")
                values.append(v)
            elif k in _JSONB_COLUMNS:
                set_clauses.append(f"{k} = %s::jsonb")
                values.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
            elif k in _ARRAY_COLUMNS:
                set_clauses.append(f"{k} = %s::text[]")
                values.append(v if isinstance(v, list) else [v])
            else:
                set_clauses.append(f"{k} = %s")
                values.append(v)
        values.append(id)

        self.execute(
            f"UPDATE items SET {', '.join(set_clauses)} WHERE id = %s",
            tuple(values),
        )
        self._commit()

    def get_items_by_status(self, status: str, limit: int = 1000) -> list[dict]:
        return self._query(
            "SELECT * FROM items WHERE status = %s ORDER BY created_at LIMIT %s",
            (status, limit),
        )

    def get_existing_urls(self) -> set[str]:
        rows = self._query("SELECT url FROM items")
        return {r["url"] for r in rows}

    def get_items_for_enrich(self, limit: int = 500, per_source: int = 40) -> list[dict]:
        """Return up to *limit* new items, with at most *per_source* from any single source."""
        return self._query(
            "SELECT * FROM ("
            "  SELECT *, ROW_NUMBER() OVER (PARTITION BY source ORDER BY created_at) AS rn "
            "  FROM items WHERE status = 'new'"
            ") sub WHERE rn <= %s ORDER BY created_at LIMIT %s",
            (per_source, limit),
        )

    # ------------------------------------------------------------------
    # Run Log
    # ------------------------------------------------------------------

    def log_run(
        self,
        run_id: str,
        stage: str,
        status: str,
        item_count: int = 0,
        duration_ms: int = 0,
        error: str | None = None,
        trigger_type: str = "manual",
    ) -> None:
        self.execute(
            "INSERT INTO run_log (run_id, stage, status, item_count, duration_ms, error, trigger_type) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (run_id, stage, status, item_count, duration_ms, error, trigger_type),
        )
        self._commit()

    def get_run_logs(self, run_id: str) -> list[dict]:
        return self._query(
            "SELECT * FROM run_log WHERE run_id = %s ORDER BY id",
            (run_id,),
        )

    def get_last_successful_run(self) -> str | None:
        rows = self._query(
            "SELECT run_id FROM run_log WHERE stage = 'backtest' AND status = 'ok' "
            "ORDER BY id DESC LIMIT 1"
        )
        return rows[0]["run_id"] if rows else None

    # ------------------------------------------------------------------
    # Conclusions
    # ------------------------------------------------------------------

    def upsert_conclusion(
        self,
        id: str,
        statement: str,
        domain: str,
        confidence: float,
        embedding: list[float],
        change_description: str | None = None,
        triggered_by: Any = None,
        conclusion_type: str = "descriptive",
        category: str = "",
    ) -> None:
        existing = self.get_conclusion(id)
        if existing:
            if (
                existing["statement"] != statement
                or existing["confidence"] != confidence
            ):
                versions = self.get_conclusion_versions(id)
                new_version = (versions[-1]["version"] + 1) if versions else 1
                self.execute(
                    "INSERT INTO conclusion_versions "
                    "(conclusion_id, version, statement, confidence, "
                    "change_description, triggered_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
                    (
                        id,
                        new_version,
                        statement,
                        confidence,
                        change_description,
                        json.dumps(triggered_by) if triggered_by else None,
                    ),
                )
                self.execute(
                    "UPDATE conclusions SET statement = %s, domain = %s, "
                    "confidence = %s, embedding = %s::vector, conclusion_type = %s, category = %s WHERE id = %s",
                    (statement, domain, confidence, embedding, conclusion_type, category, id),
                )
        else:
            self.execute(
                "INSERT INTO conclusions "
                "(id, statement, domain, confidence, embedding, conclusion_type, category) "
                "VALUES (%s, %s, %s, %s, %s::vector, %s, %s)",
                (id, statement, domain, confidence, embedding, conclusion_type, category),
            )
            self.execute(
                "INSERT INTO conclusion_versions "
                "(conclusion_id, version, statement, confidence, "
                "change_description, triggered_by) "
                "VALUES (%s, 1, %s, %s, %s, %s::jsonb)",
                (
                    id,
                    statement,
                    confidence,
                    change_description,
                    json.dumps(triggered_by) if triggered_by else None,
                ),
            )
        self._commit()

    def get_conclusion(self, id: str) -> dict | None:
        rows = self._query(
            "SELECT * FROM conclusions WHERE id = %s", (id,)
        )
        return rows[0] if rows else None

    def get_conclusion_versions(self, conclusion_id: str) -> list[dict]:
        return self._query(
            "SELECT * FROM conclusion_versions "
            "WHERE conclusion_id = %s ORDER BY version",
            (conclusion_id,),
        )

    def get_all_conclusions(self, status: str = "active") -> list[dict]:
        return self._query(
            "SELECT * FROM conclusions WHERE status = %s ORDER BY created_at DESC",
            (status,),
        )

    def get_confirmation_stats(self) -> dict:
        """Return confirmation statistics for predictive conclusions."""
        rows = self._query(
            "SELECT user_confirmation, COUNT(*) as cnt "
            "FROM conclusions "
            "WHERE status = 'active' AND conclusion_type = 'predictive' "
            "GROUP BY user_confirmation"
        )
        stats = {"confirmed": 0, "challenged": 0, "unmarked": 0}
        for r in rows:
            key = r["user_confirmation"] or "unmarked"
            if key in stats:
                stats[key] = r["cnt"]
        stats["total"] = sum(stats.values())
        return stats

    def get_active_conclusions_with_embeddings(self) -> list[dict]:
        """Return active conclusions that have embeddings (for cross-run matching)."""
        return self._query(
            "SELECT id, statement, domain, confidence, embedding "
            "FROM conclusions WHERE status = 'active' AND embedding IS NOT NULL"
        )

    def add_triggered_by(self, conclusion_id: str, item_id: str) -> None:
        """Append an item_id to the latest version's triggered_by list."""
        versions = self.get_conclusion_versions(conclusion_id)
        if not versions:
            return
        latest = versions[-1]
        triggered = latest.get("triggered_by") or []
        if isinstance(triggered, str):
            triggered = json.loads(triggered) if triggered else []
        triggered.append({"item_id": item_id[:12]})
        self.execute(
            "UPDATE conclusion_versions SET triggered_by = %s::jsonb WHERE id = %s",
            (json.dumps(triggered), latest["id"]),
        )
        self._commit()

    def merge_conclusion(self, from_id: str, into_id: str) -> None:
        """Merge one conclusion into another, recording lineage."""
        merged_from = self._query(
            "SELECT merged_from FROM conclusions WHERE id = %s", (into_id,)
        )
        current = merged_from[0].get("merged_from") if merged_from else None
        if isinstance(current, str):
            current = json.loads(current)
        if not current:
            current = []
        if from_id not in current:
            current.append(from_id)
        self.execute(
            "UPDATE conclusions SET merged_from = %s::text[] WHERE id = %s",
            (current, into_id),
        )
        self.execute(
            "UPDATE conclusions SET merged_into = %s, status = 'merged' WHERE id = %s",
            (into_id, from_id),
        )
        self._commit()

    def confirm_conclusion(self, id: str, confirmation: str) -> None:
        if confirmation not in ("confirmed", "challenged"):
            raise ValueError(
                f"confirmation must be 'confirmed' or 'challenged', got {confirmation!r}"
            )
        self.execute(
            "UPDATE conclusions SET user_confirmation = %s WHERE id = %s",
            (confirmation, id),
        )
        self._commit()

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------

    def insert_prediction(
        self,
        item_id: str,
        statement: str,
        deadline: str,
        outcome_var: str | None = None,
    ) -> str:
        pred_id = str(uuid.uuid4())
        self.execute(
            "INSERT INTO predictions (id, item_id, statement, deadline, outcome_var) "
            "VALUES (%s, %s, %s, %s, %s)",
            (pred_id, item_id, statement, deadline, outcome_var),
        )
        self._commit()
        return pred_id

    def get_pending_predictions(self) -> list[dict]:
        return self._query(
            "SELECT * FROM predictions "
            "WHERE backtest_result IS NULL AND deadline <= CURRENT_DATE"
        )

    def update_prediction_result(
        self, id: str, result: str, reason: str = ""
    ) -> None:
        self.execute(
            "UPDATE predictions SET backtest_result = %s, backtest_reason = %s, "
            "backtest_at = now() WHERE id = %s",
            (result, reason, id),
        )
        self._commit()

    def get_all_predictions(self, filter_status: str = "all") -> list[dict]:
        if filter_status == "pending":
            return self._query(
                "SELECT * FROM predictions "
                "WHERE backtest_result IS NULL ORDER BY deadline"
            )
        elif filter_status == "verified":
            return self._query(
                "SELECT * FROM predictions "
                "WHERE backtest_result IS NOT NULL ORDER BY deadline"
            )
        return self._query("SELECT * FROM predictions ORDER BY deadline")
