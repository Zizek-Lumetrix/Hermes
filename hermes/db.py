import sqlite3
from typing import Any


CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    source TEXT,
    title TEXT,
    url TEXT,
    content TEXT,
    published_at TEXT,
    simhash TEXT,
    cluster_id TEXT,
    relevance_score INTEGER,
    relevance_reason TEXT,
    analysis TEXT,
    linked_notes TEXT,
    status TEXT DEFAULT 'new',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS feedback (
    item_id TEXT PRIMARY KEY,
    rating INTEGER,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    stage TEXT,
    status TEXT,
    item_count INTEGER,
    duration_ms INTEGER,
    error TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(CREATE_TABLES)
        self.conn.commit()

    def insert_item(self, id: str, source: str, title: str, url: str,
                    content: str, published_at: str | None) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO items (id, source, title, url, content, published_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (id, source, title, url, content, published_at),
        )
        self.conn.commit()

    def update_item(self, id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [id]
        self.conn.execute(f"UPDATE items SET {sets} WHERE id = ?", values)
        self.conn.commit()

    def get_items_by_status(self, status: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM items WHERE status = ? ORDER BY created_at", (status,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_item_count_by_cluster(self, cluster_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM items WHERE cluster_id = ? AND status != 'skipped'",
            (cluster_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    def log_run(self, run_id: str, stage: str, status: str,
                item_count: int, duration_ms: int, error: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO run_log (run_id, stage, status, item_count, duration_ms, error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, stage, status, item_count, duration_ms, error),
        )
        self.conn.commit()

    def get_run_logs(self, run_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM run_log WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_last_successful_run(self) -> str | None:
        row = self.conn.execute(
            "SELECT run_id FROM run_log WHERE stage = 'write' AND status = 'ok' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["run_id"] if row else None

    def insert_feedback(self, item_id: str, rating: int) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO feedback (item_id, rating, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (item_id, rating),
        )
        self.conn.commit()

    def get_all_feedback(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM feedback").fetchall()
        return [dict(r) for r in rows]
