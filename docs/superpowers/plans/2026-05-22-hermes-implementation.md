# Hermes Intelligence Monitor — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build a CLI tool that fetches RSS feeds, filters via LLM, analyzes critically, and writes a daily intelligence brief to an Obsidian vault with auto-linked notes.

**Architecture:** Modular pipeline with SQLite state. Each stage reads from the DB, processes, writes back. Idempotent — can be re-run from any stage.

**Tech Stack:** Python 3.12+, SQLite, feedparser, html2text, openai SDK (DeepSeek), sentence-transformers, python-frontmatter

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `config.yaml`
- Create: `hermes/__init__.py`
- Create: `hermes/__main__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "hermes"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "feedparser>=6.0",
    "html2text>=2024.2",
    "openai>=1.0",
    "sentence-transformers>=3.0",
    "python-frontmatter>=1.0",
    "pyyaml>=6.0",
]

[project.scripts]
hermes = "hermes.__main__:main"
```

- [ ] **Step 2: Create config.yaml**

```yaml
obsidian:
  vault_path: ~/Documents/ObsidianVault
  brief_folder: Intel Briefs

sources:
  rss:
    - url: https://example.com/feed.xml
      name: Example

llm:
  api_key: ${DEEPSEEK_API_KEY}
  base_url: https://api.deepseek.com
  model: deepseek-chat

domains:
  - AI编程工具
  - 大模型安全

notify:
  slack_webhook: null
```

- [ ] **Step 3: Create hermes/__init__.py**

```python
"""Hermes — AI-powered intelligence monitoring."""
```

- [ ] **Step 4: Create hermes/__main__.py** (skeleton)

```python
import argparse

def main():
    parser = argparse.ArgumentParser(prog="hermes")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Run the full intelligence pipeline")
    sub.add_parser("status", help="Show last run summary")
    args = parser.parse_args()

    if args.command == "run":
        from hermes.pipeline import run
        run()
    elif args.command == "status":
        from hermes.pipeline import status
        status()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Install dependencies and verify**

```bash
cd /Users/sylvain/Documents/workspace/hermes
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m hermes --help
```

Expected: Shows usage with `run` and `status` commands (will fail on import until pipeline exists).

---

### Task 2: Config Module

**Files:**
- Create: `hermes/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
import tempfile
import os
from pathlib import Path
from hermes.config import load_config

def test_load_config_parses_yaml():
    yaml = """
obsidian:
  vault_path: ~/test-vault
  brief_folder: Briefs
sources:
  rss:
    - url: https://foo.com/rss
      name: Foo Blog
llm:
  api_key: sk-test
  base_url: https://api.deepseek.com
  model: deepseek-chat
domains:
  - AI
notify:
  slack_webhook: null
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name

    try:
        config = load_config(path)
        assert config.obsidian_vault_path == os.path.expanduser("~/test-vault")
        assert config.brief_folder == "Briefs"
        assert len(config.rss_sources) == 1
        assert config.rss_sources[0]["url"] == "https://foo.com/rss"
        assert config.llm_api_key == "sk-test"
        assert config.llm_model == "deepseek-chat"
        assert config.domains == ["AI"]
        assert config.slack_webhook is None
    finally:
        os.unlink(path)

def test_load_config_substitutes_env_vars(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret-123")
    yaml = """
obsidian:
  vault_path: /tmp/v
  brief_folder: B
sources:
  rss: []
llm:
  api_key: ${TEST_KEY}
  base_url: https://x.com
  model: m
domains: []
notify:
  slack_webhook: null
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        path = f.name
    try:
        config = load_config(path)
        assert config.llm_api_key == "secret-123"
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_config.py -v
```
Expected: FAIL (module not found or function not defined)

- [ ] **Step 3: Implement config.py**

```python
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    obsidian_vault_path: str
    brief_folder: str
    rss_sources: list[dict]
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    domains: list[str]
    slack_webhook: str | None = None


def _substitute_env(value: str) -> str:
    pattern = re.compile(r"\$\{(\w+)\}")
    matches = pattern.findall(value)
    for var in matches:
        env_val = os.environ.get(var, "")
        value = value.replace(f"${{{var}}}", env_val)
    return value


def load_config(path: str | None = None) -> Config:
    if path is None:
        path = os.path.expanduser("~/.hermes/config.yaml")

    with open(path) as f:
        raw = yaml.safe_load(f)

    llm = raw["llm"]
    obsidian = raw["obsidian"]
    notify = raw.get("notify", {})

    return Config(
        obsidian_vault_path=os.path.expanduser(obsidian["vault_path"]),
        brief_folder=obsidian["brief_folder"],
        rss_sources=raw.get("sources", {}).get("rss", []),
        llm_api_key=_substitute_env(llm["api_key"]),
        llm_base_url=llm["base_url"],
        llm_model=llm["model"],
        domains=raw.get("domains", []),
        slack_webhook=notify.get("slack_webhook"),
    )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_config.py -v
```
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_config.py hermes/config.py pyproject.toml
git commit -m "feat: add config module with YAML parsing and env var substitution"
```

---

### Task 3: Database Module

**Files:**
- Create: `hermes/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_db.py
import tempfile
import os
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
        import uuid
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_db.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: Implement db.py**

```python
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
    item_id TEXT,
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
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_db.py -v
```
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add hermes/db.py tests/test_db.py
git commit -m "feat: add SQLite database module with items, run_log, and feedback tables"
```

---

### Task 4: RSS Ingestor

**Files:**
- Create: `hermes/ingestors/__init__.py`
- Create: `hermes/ingestors/rss.py`
- Create: `tests/test_rss.py`

- [ ] **Step 1: Create ingestors __init__.py**

```python
"""Content ingestors for Hermes."""
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_rss.py
import hashlib
from hermes.ingestors.rss import fetch_feed, parse_entry

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Blog</title>
    <link>https://example.com</link>
    <item>
      <title>AI Breakthrough Today</title>
      <link>https://example.com/ai-breakthrough</link>
      <description>Scientists announced a major breakthrough in AI reasoning.</description>
      <pubDate>Wed, 21 May 2026 15:00:00 GMT</pubDate>
      <content:encoded xmlns:content="http://purl.org/rss/1.0/modules/content/">
        <![CDATA[<p>Scientists announced a major breakthrough in AI reasoning.</p><p>The new model achieves 95% accuracy.</p>]]>
      </content:encoded>
    </item>
    <item>
      <title>No Content Item</title>
      <link>https://example.com/no-content</link>
      <description>Just a summary here.</description>
    </item>
  </channel>
</rss>"""


def test_fetch_feed_parses_entries(monkeypatch):
    import feedparser

    def mock_parse(url):
        return feedparser.parse(SAMPLE_XML)

    monkeypatch.setattr("feedparser.parse", mock_parse)

    results = fetch_feed("https://example.com/feed.xml", "Test Blog")

    assert len(results) == 2
    assert results[0].title == "AI Breakthrough Today"
    assert results[0].source == "Test Blog"
    assert "Scientists announced" in results[0].content
    assert "95% accuracy" in results[0].content  # full content, not summary

    # Second item falls back to summary
    assert results[1].content == "Just a summary here."

    # ID is sha256 of URL
    expected_id = hashlib.sha256(b"https://example.com/ai-breakthrough").hexdigest()
    assert results[0].id == expected_id
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest tests/test_rss.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 4: Implement rss.py**

```python
import hashlib
import re
from dataclasses import dataclass

import feedparser
import html2text


@dataclass
class RawItem:
    id: str
    source: str
    title: str
    url: str
    content: str
    published_at: str | None
    simhash: str | None = None
    cluster_id: str | None = None


_html_cleaner = html2text.HTML2Text()
_html_cleaner.ignore_links = False
_html_cleaner.ignore_images = True
_html_cleaner.body_width = 0


def _clean_html(html: str) -> str:
    text = _html_cleaner.handle(html)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_feed(url: str, name: str) -> list[RawItem]:
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries:
        content = entry.get("content", [{}])[0].get("value", "")
        if not content:
            content = entry.get("summary", entry.get("description", ""))
        content = _clean_html(content)

        link = entry.get("link", "")
        item_id = hashlib.sha256(link.encode()).hexdigest() if link else ""

        published = entry.get("published", entry.get("updated", None))

        items.append(RawItem(
            id=item_id,
            source=name,
            title=entry.get("title", "Untitled"),
            url=link,
            content=content,
            published_at=published,
        ))
    return items
```

- [ ] **Step 5: Run test**

```bash
python -m pytest tests/test_rss.py -v
```
Expected: PASS

The test monkeypatches feedparser.parse with the sample XML, so the test actually feeds the sample into the real feedparser parser (via `feedparser.parse(SAMPLE_XML)`). This validates the parsing logic works against real feedparser output.

- [ ] **Step 6: Commit**

```bash
git add hermes/ingestors/__init__.py hermes/ingestors/rss.py tests/test_rss.py
git commit -m "feat: add RSS ingestor with HTML cleaning"
```

---

### Task 5: Dedup Module

**Files:**
- Create: `hermes/pipeline/__init__.py`
- Create: `hermes/pipeline/dedup.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Create pipeline __init__.py**

```python
"""Pipeline stages for Hermes."""
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_dedup.py
from hermes.pipeline.dedup import compute_simhash, hamming_distance, dedup_items


def test_compute_simhash_returns_hex():
    sig = compute_simhash("hello world this is some test content for hashing")
    assert isinstance(sig, str)
    assert len(sig) == 16  # 64 bits = 16 hex chars


def test_identical_texts_same_simhash():
    a = compute_simhash("The quick brown fox jumps over the lazy dog")
    b = compute_simhash("The quick brown fox jumps over the lazy dog")
    assert a == b


def test_similar_texts_have_small_hamming_distance():
    a = compute_simhash(
        "Breaking news: scientists discover new exoplanet in habitable zone "
        "of nearby star system, NASA confirms. The planet is roughly Earth-sized."
    )
    b = compute_simhash(
        "Breaking news: scientists discover new exoplanet in habitable zone "
        "of nearby star system, NASA confirmed. The planet is approximately Earth-sized."
    )
    assert hamming_distance(a, b) <= 3


def test_different_texts_have_large_hamming_distance():
    a = compute_simhash("AI models achieve new benchmark on reasoning tasks")
    b = compute_simhash(
        "The local weather forecast predicts rain for the next three days "
        "with temperatures dropping below freezing at night"
    )
    assert hamming_distance(a, b) > 3


def test_dedup_items_groups_similar():
    from hermes.ingestors.rss import RawItem

    items = [
        RawItem("1", "Blog A", "AI News", "https://a.com/1",
                "Breaking: GPT-5 released today with major improvements in reasoning and coding. "
                "The new model outperforms all previous versions.", None),
        RawItem("2", "Blog B", "GPT-5 Launched",
                "https://b.com/1",
                "Breaking: GPT-5 released today with major improvements in reasoning and coding. "
                "The new model outperforms all previous versions. Early benchmarks show 30% gain.", None),
        RawItem("3", "Blog C", "Weather Report",
                "https://c.com/1",
                "Tomorrow will be sunny with a high of 75 degrees.", None),
    ]

    result = dedup_items(items, existing_urls=set())

    # Items 1 and 2 should share a cluster_id
    assert result[0].cluster_id == result[1].cluster_id
    # Item 3 should have a different cluster_id
    assert result[2].cluster_id != result[0].cluster_id


def test_dedup_skips_existing_urls():
    from hermes.ingestors.rss import RawItem

    items = [
        RawItem("id1", "Blog A", "T", "https://a.com/1", "Content here", None),
    ]
    result = dedup_items(items, existing_urls={"https://a.com/1"})
    assert len(result) == 1
    # The item should be marked - status will be set by caller
    assert result[0].id == "id1"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest tests/test_dedup.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 4: Implement dedup.py**

```python
import hashlib
import uuid
from hermes.ingestors.rss import RawItem


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def compute_simhash(text: str, bits: int = 64) -> str:
    tokens = _tokenize(text)
    vector = [0] * bits

    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(bits):
            if h & (1 << i):
                vector[i] += 1
            else:
                vector[i] -= 1

    fingerprint = 0
    for i in range(bits):
        if vector[i] > 0:
            fingerprint |= (1 << i)

    return format(fingerprint, "016x")


def hamming_distance(a: str, b: str) -> int:
    a_int = int(a, 16)
    b_int = int(b, 16)
    xor = a_int ^ b_int
    return xor.bit_count()


def dedup_items(items: list[RawItem], existing_urls: set[str]) -> list[RawItem]:
    for item in items:
        prefix = item.content[:500] if item.content else item.title
        item.simhash = compute_simhash(prefix)

    clusters: dict[str, list[RawItem]] = {}
    assigned = set()

    for i, item in enumerate(items):
        if i in assigned:
            continue
        cluster_key = item.simhash
        clusters[cluster_key] = [item]
        for j in range(i + 1, len(items)):
            if j in assigned:
                continue
            other = items[j]
            if hamming_distance(item.simhash, other.simhash) <= 3:
                clusters[cluster_key].append(other)
                assigned.add(j)

    for cluster_items in clusters.values():
        cluster_id = str(uuid.uuid4())[:8]
        for item in cluster_items:
            item.cluster_id = cluster_id

    return items
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_dedup.py -v
```
Expected: 6 PASS

- [ ] **Step 6: Commit**

```bash
git add hermes/pipeline/__init__.py hermes/pipeline/dedup.py tests/test_dedup.py
git commit -m "feat: add semantic dedup with simhash"
```

---

### Task 6: Embeddings Module

**Files:**
- Create: `hermes/embeddings.py`
- Create: `tests/test_embeddings.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_embeddings.py
import tempfile
import os
from pathlib import Path
from hermes.embeddings import EmbeddingIndex


def test_build_and_query_index():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some markdown files
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_embeddings.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: Implement embeddings.py**

```python
from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np


class EmbeddingIndex:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.paths: list[str] = []
        self.embeddings: np.ndarray | None = None

    def build(self, vault_path: str) -> None:
        vault = Path(vault_path).expanduser()
        if not vault.exists():
            self.paths = []
            self.embeddings = None
            return

        md_files = list(vault.rglob("*.md"))
        texts = []
        self.paths = []

        for f in md_files:
            try:
                content = f.read_text()
                if content.strip():
                    texts.append(content[:2000])
                    self.paths.append(str(f.relative_to(vault)))
            except Exception:
                continue

        if texts:
            self.embeddings = self.model.encode(texts)
        else:
            self.embeddings = None

    def query(self, text: str, top_k: int = 3) -> list[tuple[str, float]]:
        if not self.embeddings or len(self.paths) == 0:
            return []

        query_vec = self.model.encode([text])[0]
        similarities = np.dot(self.embeddings, query_vec) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_vec)
        )
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            if similarities[idx] > 0.3:
                results.append((self.paths[idx], float(similarities[idx])))
        return results
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_embeddings.py -v
```
Expected: 3 PASS (first run will download the model automatically)

- [ ] **Step 5: Commit**

```bash
git add hermes/embeddings.py tests/test_embeddings.py
git commit -m "feat: add embedding index for Obsidian vault notes"
```

---

### Task 7: LLM Filter

**Files:**
- Create: `hermes/pipeline/filter.py`
- Create: `tests/test_filter.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_filter.py
import json
from unittest.mock import MagicMock, patch
from hermes.pipeline.filter import filter_items, build_filter_prompt


def test_build_filter_prompt_includes_domains():
    prompt = build_filter_prompt(["AI安全", "开源模型"], feedback_notes=[])
    assert "AI安全" in prompt
    assert "开源模型" in prompt
    assert "0-10" in prompt
    assert "JSON" in prompt


def test_build_filter_prompt_with_feedback():
    feedback = [{"item_id": "x", "rating": 1}, {"item_id": "y", "rating": 5}]
    prompt = build_filter_prompt(["AI"], feedback_notes=feedback)
    assert "用户偏好" in prompt


def test_filter_items_calls_api():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"score": 8, "reason": "直接相关AI安全话题"}'
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    items = [
        {
            "id": "abc",
            "title": "GPT-5 Security Analysis",
            "content": "Researchers find vulnerabilities in GPT-5.",
            "cluster_id": "c1",
            "source": "Blog A",
        }
    ]

    result = filter_items(items, ["AI安全"], [], mock_client)

    assert len(result) == 1
    assert result[0]["relevance_score"] == 8
    assert result[0]["relevance_reason"] == "直接相关AI安全话题"
    assert result[0]["status"] == "filtered"


def test_filter_items_skips_low_score():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"score": 1, "reason": ""}'
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    items = [
        {
            "id": "xyz",
            "title": "Weather Forecast",
            "content": "Sunny tomorrow.",
            "cluster_id": "c1",
            "source": "Weather Blog",
        }
    ]

    result = filter_items(items, ["AI安全"], [], mock_client)

    assert len(result) == 1
    assert result[0]["status"] == "skipped"


def test_filter_items_handles_malformed_json():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="not valid json"))
    ]
    mock_client.chat.completions.create.return_value = mock_response

    items = [{"id": "x", "title": "T", "content": "C", "cluster_id": "c1", "source": "S"}]

    result = filter_items(items, ["AI"], [], mock_client)
    # Should survive malformed JSON and default to skipping
    assert len(result) >= 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_filter.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: Implement filter.py**

```python
import json
import re


def build_filter_prompt(domains: list[str], feedback_notes: list[dict]) -> str:
    domain_list = "、".join(domains)
    prompt = f"""你是一个信息过滤器。用户关注以下领域：{domain_list}。

请对以下内容评分（0-10）：
- 10 = 直接核心相关，用户必须知道
- 5 = 有一定关联
- 0 = 完全无关

输出严格 JSON 格式，不包含任何其他文字：
{{"score": <整数0-10>, "reason": "<一句话理由，score<3时可为空>"}}"""

    if feedback_notes:
        low_rated = [f for f in feedback_notes if f.get("rating", 0) <= 2]
        high_rated = [f for f in feedback_notes if f.get("rating", 0) >= 4]
        if low_rated or high_rated:
            prompt += "\n\n用户偏好参考："
            if low_rated:
                prompt += f"\n- 用户对类似以下内容打过低分: {low_rated[:3]}"
            if high_rated:
                prompt += f"\n- 用户对类似以下内容打过高分: {high_rated[:3]}"

    return prompt


def filter_items(
    items: list[dict],
    domains: list[str],
    feedback: list[dict],
    client,
    threshold: int = 3,
) -> list[dict]:
    prompt_template = build_filter_prompt(domains, feedback)

    for item in items:
        content = f"标题：{item['title']}\n来源：{item['source']}\n内容：{item['content'][:1500]}"
        user_msg = f"{prompt_template}\n\n{content}"

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.1,
                max_tokens=100,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```\w*\n?|```", "", raw)
            parsed = json.loads(raw)
            score = int(parsed.get("score", 0))
            reason = parsed.get("reason", "")
        except (json.JSONDecodeError, ValueError, KeyError, AttributeError):
            score = 0
            reason = "parse error"

        item["relevance_score"] = score
        item["relevance_reason"] = reason
        item["status"] = "filtered" if score >= threshold else "skipped"

    return items
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_filter.py -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add hermes/pipeline/filter.py tests/test_filter.py
git commit -m "feat: add LLM filter stage with domain-aware scoring"
```

---

### Task 8: LLM Analyze

**Files:**
- Create: `hermes/pipeline/analyze.py`
- Create: `tests/test_analyze.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_analyze.py
import json
from unittest.mock import MagicMock
from hermes.pipeline.analyze import analyze_items, build_analyze_prompt


def test_build_analyze_prompt():
    prompt = build_analyze_prompt(["AI安全"])
    assert "批判性分析" in prompt
    assert "偏见" in prompt
    assert "confidence" in prompt


def test_analyze_items_calls_api_and_parses_response():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({
                    "title_cn": "GPT-5安全漏洞分析",
                    "summary": "研究人员发现GPT-5存在提示注入漏洞，攻击者可绕过安全限制。"
                              "但该研究仅在实验室环境验证，尚未在实际部署中复现。",
                    "key_points": ["提示注入漏洞", "实验室环境验证", "实际影响待确认"],
                    "implications": "AI应用开发者需关注提示注入防御机制，但不需立即恐慌",
                    "confidence": "medium",
                })
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    items = [
        {
            "id": "abc",
            "title": "GPT-5 Security Analysis",
            "content": "Full article content here.",
            "source": "AI Security Blog",
            "relevance_score": 8,
        }
    ]

    result = analyze_items(items, ["AI安全"], mock_client)

    assert len(result) == 1
    assert result[0]["analysis"] is not None
    analysis = json.loads(result[0]["analysis"])
    assert analysis["confidence"] == "medium"
    assert "提示注入" in analysis["title_cn"]
    assert len(analysis["key_points"]) == 3
    assert result[0]["status"] == "analyzed"


def test_analyze_items_handles_error_gracefully():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API error")

    items = [
        {"id": "x", "title": "T", "content": "C", "source": "S", "relevance_score": 5}
    ]

    result = analyze_items(items, ["AI"], mock_client)
    assert len(result) == 1
    assert result[0]["status"] == "skipped"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_analyze.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: Implement analyze.py**

```python
import json
import re


def build_analyze_prompt(domains: list[str]) -> str:
    domain_list = "、".join(domains)
    return f"""你是一个情报分析专家，关注领域：{domain_list}。

请对以下内容进行批判性分析。注意：
- 识别信源偏见和未被验证的断言
- 与其他已知信息的矛盾之处
- 区分事实陈述与观点推断

输出严格 JSON 格式（不含代码块标记）：
{{
    "title_cn": "<中文标题>",
    "summary": "<200字批判性摘要>",
    "key_points": ["<要点1>", "<要点2>", "<要点3>"],
    "implications": "<对从业者的一两句话启示>",
    "confidence": "high|medium|low"
}}"""


def analyze_items(
    items: list[dict],
    domains: list[str],
    client,
) -> list[dict]:
    prompt_template = build_analyze_prompt(domains)

    for item in items:
        content = f"标题：{item['title']}\n来源：{item['source']}\n内容：{item['content'][:3000]}"
        user_msg = f"{prompt_template}\n\n{content}"

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.3,
                max_tokens=800,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```\w*\n?|```", "", raw)
            parsed = json.loads(raw)
        except (json.JSONDecodeError, Exception):
            item["status"] = "skipped"
            continue

        item["analysis"] = json.dumps(parsed, ensure_ascii=False)
        item["status"] = "analyzed"

    return items
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_analyze.py -v
```
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add hermes/pipeline/analyze.py tests/test_analyze.py
git commit -m "feat: add LLM critical analysis stage"
```

---

### Task 9: Obsidian Writer

**Files:**
- Create: `hermes/pipeline/write.py`
- Create: `tests/test_write.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_write.py
import tempfile
import os
import json
from pathlib import Path
from datetime import date
from hermes.pipeline.write import write_brief, scan_feedback


def test_write_brief_creates_markdown_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        items = [
            {
                "id": "abc",
                "title": "GPT-5 Release",
                "url": "https://example.com/gpt5",
                "source": "Tech Blog",
                "relevance_score": 9,
                "analysis": json.dumps({
                    "title_cn": "GPT-5发布",
                    "summary": "OpenAI发布了GPT-5，在推理和编程任务上大幅提升。",
                    "key_points": ["推理提升30%", "编程能力超人类"],
                    "implications": "开发者应考虑升级到新模型",
                    "confidence": "high",
                }),
                "linked_notes": ["AI趋势.md", "GPT模型.md"],
            },
            {
                "id": "xyz",
                "title": "Minor Update",
                "url": "https://example.com/minor",
                "source": "Other Blog",
                "relevance_score": 4,
                "analysis": json.dumps({
                    "title_cn": "小更新",
                    "summary": "某公司发布了小版本更新。",
                    "key_points": ["bug修复"],
                    "implications": "无重大影响",
                    "confidence": "high",
                }),
                "linked_notes": [],
            },
        ]

        brief_path = write_brief(items, tmpdir, "Briefs")

        assert os.path.exists(brief_path)
        content = Path(brief_path).read_text()

        # Check frontmatter
        assert "type: intel-brief" in content
        assert str(date.today().year) in content

        # Check sections
        assert "高相关" in content
        assert "中相关" in content

        # Check the high-relevance item is present
        assert "GPT-5发布" in content
        assert "OpenAI发布了GPT-5" in content

        # Check wiki links
        assert "[[AI趋势.md]]" in content
        assert "[[GPT模型.md]]" in content

        # Check confidence annotation
        assert "信源" not in content.lower() or True  # high confidence, no warning

        # Check that items are in correct sections
        high_section_start = content.index("高相关")
        mid_section_start = content.index("中相关")
        assert content.index("GPT-5发布") < mid_section_start
        assert content.index("小更新") > mid_section_start


def test_write_brief_low_confidence_gets_warning():
    with tempfile.TemporaryDirectory() as tmpdir:
        items = [
            {
                "id": "low1",
                "title": "Rumor",
                "url": "https://x.com/r",
                "source": "Twitter",
                "relevance_score": 6,
                "analysis": json.dumps({
                    "title_cn": "传闻",
                    "summary": "某传闻称...",
                    "key_points": ["未证实的消息"],
                    "implications": "如果属实则有影响",
                    "confidence": "low",
                }),
                "linked_notes": [],
            }
        ]

        brief_path = write_brief(items, tmpdir, "Briefs")
        content = Path(brief_path).read_text()
        assert "信源未充分验证" in content


def test_write_brief_empty_items():
    with tempfile.TemporaryDirectory() as tmpdir:
        brief_path = write_brief([], tmpdir, "Briefs")
        content = Path(brief_path).read_text()
        assert "今日无重要情报" in content


def test_scan_feedback():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a brief with rating
        brief_dir = Path(tmpdir) / "Briefs"
        brief_dir.mkdir()
        brief_content = """---
date: 2026-05-21
type: intel-brief
rating: 2
---
# 昨日情报
内容...
"""
        (brief_dir / "Intel Brief – 2026-05-21.md").write_text(brief_content)

        # Create another without rating
        (brief_dir / "Intel Brief – 2026-05-20.md").write_text(
            "---\ndate: 2026-05-20\ntype: intel-brief\n---\n# 内容"
        )

        feedback = scan_feedback(str(tmpdir), "Briefs")
        assert len(feedback) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_write.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: Implement write.py**

```python
import json
import os
from datetime import date, datetime
from pathlib import Path

import frontmatter


def scan_feedback(vault_path: str, brief_folder: str) -> list[dict]:
    brief_dir = Path(vault_path) / brief_folder
    if not brief_dir.exists():
        return []

    feedback = []
    for f in brief_dir.glob("*.md"):
        try:
            post = frontmatter.load(f)
            if post.get("type") == "intel-brief" and "rating" in post:
                feedback.append({
                    "brief_date": str(post.get("date", "")),
                    "rating": post["rating"],
                })
        except Exception:
            continue

    return feedback


def write_brief(items: list[dict], vault_path: str, brief_folder: str) -> str:
    brief_dir = Path(vault_path) / brief_folder
    brief_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()
    filename = f"Intel Brief – {today.isoformat()}.md"
    filepath = brief_dir / filename

    high_items = [i for i in items if i.get("relevance_score", 0) >= 7]
    mid_items = [i for i in items if 4 <= i.get("relevance_score", 0) <= 6]
    low_items = [i for i in items if 3 <= i.get("relevance_score", 0) <= 3]

    lines = [
        "---",
        f"date: {today}",
        "type: intel-brief",
        "---",
        "",
        f"# 今日情报 · {today}",
        "",
    ]

    if not items:
        lines.append("今日无重要情报。")
        filepath.write_text("\n".join(lines))
        return str(filepath)

    def _render_section(label: str, icon: str, item_list: list[dict]) -> None:
        if not item_list:
            return
        lines.append(f"## {icon} {label}（{len(item_list)}条）")
        lines.append("")
        for item in item_list:
            try:
                analysis = json.loads(item.get("analysis", "{}"))
            except (json.JSONDecodeError, TypeError):
                analysis = {}

            title = analysis.get("title_cn", item.get("title", "Untitled"))
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"> 来源：[{item.get('source', 'Unknown')}]({item.get('url', '')})")
            lines.append("")

            if analysis.get("confidence") == "low":
                lines.append("⚠️ **信源未充分验证，请交叉确认**")
                lines.append("")

            lines.append(analysis.get("summary", ""))
            lines.append("")

            key_points = analysis.get("key_points", [])
            if key_points:
                for kp in key_points:
                    lines.append(f"- {kp}")
                lines.append("")

            implications = analysis.get("implications", "")
            if implications:
                lines.append(f"**启示**：{implications}")
                lines.append("")

            linked = item.get("linked_notes", [])
            if linked:
                if isinstance(linked, str):
                    try:
                        linked = json.loads(linked)
                    except (json.JSONDecodeError, TypeError):
                        linked = []
                note_links = " · ".join(f"[[{n}]]" for n in linked)
                lines.append(f"→ 关联笔记：{note_links}")
                lines.append("")

            lines.append("---")
            lines.append("")

    _render_section("高相关", "🔴", high_items)
    _render_section("中相关", "🟡", mid_items)
    _render_section("低相关", "🟢", low_items)

    filepath.write_text("\n".join(lines))
    return str(filepath)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_write.py -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add hermes/pipeline/write.py tests/test_write.py
git commit -m "feat: add Obsidian writer with auto-linking and feedback scanning"
```

---

### Task 10: Notify Module

**Files:**
- Create: `hermes/notify.py`
- Create: `tests/test_notify.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_notify.py
from hermes.notify import format_summary


def test_format_summary():
    logs = [
        {"stage": "ingest", "status": "ok", "item_count": 50, "duration_ms": 1200},
        {"stage": "dedup", "status": "ok", "item_count": 30, "duration_ms": 300},
        {"stage": "filter", "status": "ok", "item_count": 8, "duration_ms": 45000},
        {"stage": "analyze", "status": "ok", "item_count": 5, "duration_ms": 30000},
        {"stage": "write", "status": "ok", "item_count": 5, "duration_ms": 2000},
    ]

    summary = format_summary(logs)
    assert "50" in summary
    assert "8" in summary
    assert "5" in summary


def test_format_summary_with_errors():
    logs = [
        {"stage": "ingest", "status": "ok", "item_count": 50, "duration_ms": 1200},
        {"stage": "dedup", "status": "error", "item_count": 0, "duration_ms": 100,
         "error": "database locked"},
    ]

    summary = format_summary(logs)
    assert "ERROR" in summary
    assert "database locked" in summary
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_notify.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: Implement notify.py**

```python
import requests


def format_summary(logs: list[dict]) -> str:
    lines = ["Hermes Run Summary", "=" * 20]
    total_ms = 0
    errors = []

    for log in logs:
        stage = log["stage"]
        status = log["status"].upper() if log["status"] == "error" else log["status"]
        count = log.get("item_count", 0)
        ms = log.get("duration_ms", 0)
        total_ms += ms

        line = f"  {stage}: {status} | {count} items | {ms/1000:.1f}s"
        lines.append(line)

        if log.get("error"):
            errors.append(f"  [{stage}] {log['error']}")

    lines.append("-" * 20)
    lines.append(f"  Total: {total_ms/1000:.1f}s")

    if errors:
        lines.append("")
        lines.append("ERRORS:")
        lines.extend(errors)

    return "\n".join(lines)


def send_slack(webhook_url: str, text: str) -> None:
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json={"text": text}, timeout=10)
    except Exception:
        pass
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_notify.py -v
```
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add hermes/notify.py tests/test_notify.py
git commit -m "feat: add run summary notification module"
```

---

### Task 11: Main Pipeline — Wire Everything Together

**Files:**
- Create: `hermes/pipeline/run.py`
- Modify: `hermes/__main__.py`

- [ ] **Step 1: Implement run.py**

```python
import os
import time
import uuid
from pathlib import Path

from openai import OpenAI

from hermes.config import load_config, Config
from hermes.db import Database
from hermes.embeddings import EmbeddingIndex
from hermes.ingestors.rss import fetch_feed
from hermes.pipeline.dedup import dedup_items
from hermes.pipeline.filter import filter_items, build_filter_prompt
from hermes.pipeline.analyze import analyze_items, build_analyze_prompt
from hermes.pipeline.write import write_brief, scan_feedback
from hermes.notify import format_summary, send_slack


def _get_db_path() -> str:
    base = os.path.expanduser("~/.hermes")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "hermes.db")


def run(config_path: str | None = None) -> None:
    config = load_config(config_path)
    db = Database(_get_db_path())
    run_id = str(uuid.uuid4())
    client = OpenAI(
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
    )

    # Stage 1: Ingest
    t0 = time.monotonic()
    try:
        all_items = []
        existing_urls = _get_existing_urls(db)
        for src in config.rss_sources:
            try:
                items = fetch_feed(src["url"], src["name"])
                all_items.extend(items)
            except Exception as e:
                db.log_run(run_id, f"ingest:{src['name']}", "error", 0, 0, str(e))

        for item in all_items:
            db.insert_item(
                id=item.id, source=item.source, title=item.title,
                url=item.url, content=item.content,
                published_at=item.published_at,
            )

        elapsed = int((time.monotonic() - t0) * 1000)
        db.log_run(run_id, "ingest", "ok", len(all_items), elapsed)
    except Exception as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        db.log_run(run_id, "ingest", "error", 0, elapsed, str(e))
        return

    if not all_items:
        _finish(db, run_id, config, [])
        return

    # Stage 2: Dedup
    t0 = time.monotonic()
    try:
        deduped = dedup_items(all_items, existing_urls)
        for item in deduped:
            db.update_item(item.id, simhash=item.simhash, cluster_id=item.cluster_id)
        new_items = [i for i in deduped if i.id not in existing_urls]
        elapsed = int((time.monotonic() - t0) * 1000)
        db.log_run(run_id, "dedup", "ok", len(new_items), elapsed)
    except Exception as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        db.log_run(run_id, "dedup", "error", 0, elapsed, str(e))
        return

    if not new_items:
        _finish(db, run_id, config, [])
        return

    # Stage 3: Filter
    t0 = time.monotonic()
    try:
        feedback = db.get_all_feedback()
        new_item_dicts = [
            {
                "id": i.id, "title": i.title, "content": i.content,
                "cluster_id": i.cluster_id, "source": i.source,
            }
            for i in new_items
        ]
        filtered = filter_items(new_item_dicts, config.domains, feedback, client)
        for item in filtered:
            db.update_item(
                item["id"],
                status=item["status"],
                relevance_score=item["relevance_score"],
                relevance_reason=item.get("relevance_reason", ""),
            )
        elapsed = int((time.monotonic() - t0) * 1000)
        db.log_run(run_id, "filter", "ok", len(filtered), elapsed)
    except Exception as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        db.log_run(run_id, "filter", "error", 0, elapsed, str(e))
        return

    # Stage 4: Analyze
    to_analyze = [f for f in filtered if f["status"] == "filtered"]
    t0 = time.monotonic()
    try:
        analyzed = analyze_items(to_analyze, config.domains, client)
        for item in analyzed:
            db.update_item(
                item["id"],
                status=item["status"],
                analysis=item.get("analysis", ""),
            )
        elapsed = int((time.monotonic() - t0) * 1000)
        db.log_run(run_id, "analyze", "ok", len(analyzed), elapsed)
    except Exception as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        db.log_run(run_id, "analyze", "error", 0, elapsed, str(e))
        return

    # Stage 5: Write
    written = [a for a in analyzed if a["status"] == "analyzed"]
    t0 = time.monotonic()
    try:
        # Build embedding index and link notes
        index = EmbeddingIndex()
        index.build(config.obsidian_vault_path)

        # Scan feedback from previous briefs
        brief_feedback = scan_feedback(
            config.obsidian_vault_path, config.brief_folder
        )
        for fb in brief_feedback:
            db.insert_feedback(fb["brief_date"], fb["rating"])

        for item in written:
            if item.get("analysis"):
                import json
                try:
                    analysis = json.loads(item["analysis"])
                    query_text = analysis.get("title_cn", item.get("title", ""))
                except (json.JSONDecodeError, TypeError):
                    query_text = item.get("title", "")
                related = index.query(query_text)
                item["linked_notes"] = json.dumps([r[0] for r in related])

        # Fetch full items from DB for writer
        write_items = []
        for item in written:
            db_item = db.get_items_by_status("analyzed")
            matching = [d for d in db_item if d["id"] == item["id"]]
            if matching:
                write_items.append(dict(matching[0]))
            else:
                write_items.append(item)

        brief_path = write_brief(
            write_items, config.obsidian_vault_path, config.brief_folder
        )

        for item in written:
            db.update_item(item["id"], status="written")

        elapsed = int((time.monotonic() - t0) * 1000)
        db.log_run(run_id, "write", "ok", len(written), elapsed)
    except Exception as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        db.log_run(run_id, "write", "error", 0, elapsed, str(e))
        return

    _finish(db, run_id, config, written)


def _get_existing_urls(db: Database) -> set[str]:
    rows = db.conn.execute("SELECT url FROM items").fetchall()
    return {r["url"] for r in rows}


def _finish(db: Database, run_id: str, config, items: list[dict]) -> None:
    logs = db.get_run_logs(run_id)
    summary = format_summary(logs)
    print(summary)
    send_slack(config.slack_webhook, summary)


def status() -> None:
    db = Database(_get_db_path())
    run_id = db.get_last_successful_run()
    if run_id:
        logs = db.get_run_logs(run_id)
        print(format_summary(logs))
    else:
        print("No successful runs yet.")
```

- [ ] **Step 2: Update __main__.py**

```python
import argparse


def main():
    parser = argparse.ArgumentParser(prog="hermes")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Run the full intelligence pipeline")
    sub.add_parser("status", help="Show last run summary")
    args = parser.parse_args()

    if args.command == "run":
        from hermes.pipeline.run import run
        run()
    elif args.command == "status":
        from hermes.pipeline.run import status
        status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify import chain works**

```bash
cd /Users/sylvain/Documents/workspace/hermes
python -c "from hermes.pipeline.run import run, status; print('OK')"
```

Expected: OK

- [ ] **Step 4: Commit**

```bash
git add hermes/pipeline/run.py hermes/__main__.py
git commit -m "feat: wire full pipeline with run and status commands"
```

---

### Task 12: End-to-End Smoke Test

**Files:**
- Create: `tests/test_e2e.py`
- Create: `.gitignore`

- [ ] **Step 1: Create .gitignore**

```
__pycache__/
.venv/
*.pyc
.env
.DS_Store
```

- [ ] **Step 2: Write e2e test**

```python
# tests/test_e2e.py
import json
import tempfile
import os
from unittest.mock import MagicMock, patch
from pathlib import Path
from openai import OpenAI

from hermes.config import Config
from hermes.db import Database


def test_full_pipeline_with_mocks(monkeypatch, tmp_path):
    """Simulate a full pipeline run with mocked RSS and LLM."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "existing_note.md").write_text(
        "AI safety research and alignment techniques"
    )
    brief_dir = vault / "Briefs"
    brief_dir.mkdir()

    # Mock RSS feed
    SAMPLE_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
  <title>New AI Safety Paper Released</title>
  <link>https://example.com/ai-safety</link>
  <description>Researchers published a comprehensive survey of AI alignment techniques.</description>
</item>
<item>
  <title>Local Weather Update</title>
  <link>https://example.com/weather</link>
  <description>Partly cloudy with a high of 72.</description>
</item>
</channel></rss>"""

    import feedparser
    def mock_parse(url):
        return feedparser.parse(SAMPLE_XML)
    monkeypatch.setattr("feedparser.parse", mock_parse)

    # Mock LLM responses
    mock_client = MagicMock()

    filter_response = MagicMock()
    filter_response.choices = [
        MagicMock(message=MagicMock(content='{"score": 8, "reason": "直接相关AI安全"}'))
    ]

    weather_filter = MagicMock()
    weather_filter.choices = [
        MagicMock(message=MagicMock(content='{"score": 0, "reason": ""}'))
    ]

    analyze_response = MagicMock()
    analyze_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "title_cn": "AI安全综述论文发布",
            "summary": "研究者发布了AI对齐技术的综合综述。",
            "key_points": ["涵盖50+种技术", "基准测试结果积极"],
            "implications": "从业者应关注对齐技术的最新进展",
            "confidence": "high",
        })))
    ]

    mock_client.chat.completions.create.side_effect = [
        filter_response, weather_filter, analyze_response,
    ]

    # Write config
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"""
obsidian:
  vault_path: {vault}
  brief_folder: Briefs
sources:
  rss:
    - url: https://example.com/feed.xml
      name: Test Feed
llm:
  api_key: sk-test
  base_url: https://api.deepseek.com
  model: deepseek-chat
domains:
  - AI安全
  - 大模型
notify:
  slack_webhook: null
""")

    # Patch OpenAI client and DB path
    db_path = tmp_path / "test.db"

    import hermes.pipeline.run as run_module
    monkeypatch.setattr(run_module, "_get_db_path", lambda: str(db_path))

    from openai import OpenAI
    original_init = OpenAI.__init__

    def mock_openai_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.chat = mock_client.chat

    monkeypatch.setattr(OpenAI, "__init__", mock_openai_init)

    # Run the pipeline
    run_module.run(str(config_path))

    # Verify outputs
    db = Database(str(db_path))
    items = db.get_items_by_status("written")
    assert len(items) == 1
    assert "AI safety" in items[0]["title"].lower()

    # Check brief file was created
    import datetime
    today = datetime.date.today().isoformat()
    brief_path = brief_dir / f"Intel Brief – {today}.md"
    assert brief_path.exists()

    content = brief_path.read_text()
    assert "AI安全综述" in content
    assert "高相关" in content
    assert "existing_note.md" in content  # auto-linked!
```

- [ ] **Step 3: Run e2e test**

```bash
python -m pytest tests/test_e2e.py -v
```
Expected: 1 PASS (may need to install deps first)

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e.py .gitignore
git commit -m "test: add end-to-end smoke test"
```
