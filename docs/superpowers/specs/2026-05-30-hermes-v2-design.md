# Hermes v2 Design Spec

**Date:** 2026-05-30
**Status:** Draft
**Reviewers:** Musk (engineering pragmatism), Karpathy (AI architecture), Ben Wintle (product sustainability), Crystal Lee Gonzalez (local infrastructure)

## Overview

Hermes v2 transforms from a static markdown intelligence brief generator into a **living personal knowledge graph** — a continuously updated world model that tracks conclusions, verifies predictions, and shows how new information changes understanding over time.

**Input:** RSS feeds + Obsidian vault (web clipper distilled content and personal notes)
**Output:** Single-page web application showing a knowledge graph, cognitive update stream, and prediction scorecard

## v1 Scope Decision

v1 delivers the **minimum core loop**: information enters → conclusions update → user sees changes → system tracks prediction accuracy. All reviewers converged on this.

### v1 Must-Have (12 items)

| # | Feature | Rationale |
|---|---------|-----------|
| 1 | RSS Ingest + Obsidian vault reading | Primary inputs |
| 2 | Dedup (simhash + URL) | Keep existing, remove noise |
| 3 | Enrich (vector embedding + streaming clustering) | Foundation for all downstream intelligence. Cold-start with existing vault + historical RSS |
| 4 | Pre-filter (rule layer + LLM binary classification) | Rules cut ~50% at zero cost, LLM handles the rest |
| 5 | Analyze (two LLM calls: critique + structure extraction with verifiable predictions) | Separate writing (t=0.3) from extraction (t=0.1) for reliability. Entities stored as JSONB, no entity resolution |
| 6 | Post-filter (exploit_score only) | Relevance scoring on analyzed items. Surprise score deferred to v1.1 |
| 7 | Synthesize (density peak clustering → LLM explanation) | Data-first: cluster in embedding space, LLM explains why clusters exist. Minimum 15 items to cluster. One representative per near-duplicate cluster |
| 8 | Prediction Backtester (triggered, not periodic) | Structurable predictions → external data verification. Non-structurable → generate observable signals |
| 9 | Conclusion version history | Append new version when information affects existing conclusions. Track confidence changes |
| 10 | Single-page Web UI | D3 force graph (top) + cognitive update stream (bottom) + prediction scorecard integrated. Click node → drawer with details and version history |
| 11 | User confirmation mechanism | Each conclusion: "confirmed" or "challenged" toggle. Confirmation/challenge ratio as trust proxy for first 30 days |
| 12 | Weekly health check email | Ingest count, new conclusions, errors. One curl + cron |

### Deferred to v1.1

| # | Feature | Reason |
|---|---------|--------|
| 13 | Surprise score (exploration track) | Stabilize exploit loop first |
| 14 | Entity resolution (entities table + item_entities) | Dirtiest NLP problem. JSONB is enough for v1 |
| 15 | Blindspot scanning | Requires dense conclusion space |
| 16 | Multiple pages | Unnecessary for single-user system |

### Explicitly Cut (v2+)

| # | Feature | Reason |
|---|---------|--------|
| 17 | Agent execution (auto-actions, checklists) | Maturity not there yet |
| 18 | Multi-user support | One-person infrastructure by design |
| 19 | Facebook/Twitter/YouTube sources | Add per-channel based on information density |
| 20 | Mobile app | Web responsive is sufficient |

## Architecture

```
                      INPUT LAYER
   RSS sources ──┐
                 ├──→ Ingest ──→ Dedup ──→ Enrich
   Obsidian ─────┘                        (embedding +
   vault (web                              streaming
   clipper, notes)                         clustering)
                                               │
                      INTELLIGENCE LAYER        │
   ┌───────────────────────────────────────────┘
   │
   ├──→ Pre-filter ──→ Analyze ──→ Post-filter ──→ Synthesize
   │    (rules+LLM      (2 LLM       (exploit         (density
   │     binary)         calls)       score)           clustering
   │                                                    → LLM explain)
   │
   └──→ Prediction Backtester (triggered on each run)
            │
            ▼
                      KNOWLEDGE LAYER
   PostgreSQL + pgvector
   ├── items (with embedding, implicit_cluster, analysis JSONB, prediction JSONB)
   ├── conclusions (with version history via conclusion_versions)
   ├── predictions (with backtest results)
   └── run_log (observability)

                      PRESENTATION LAYER
   FastAPI (read-only REST) → Single page HTML/D3.js
   ├── Knowledge graph (force-directed, time slider, drawer)
   ├── Cognitive update stream (reverse chrono, type filter)
   └── Prediction scorecard (embedded)
```

## Pipeline Stages

### Stage 0: Enrich (NEW)
- Compute 384d embedding via all-MiniLM-L6-v2 per item
- Streaming clustering: maintain centroid list, assign item to nearest centroid or create new cluster if distance exceeds threshold
- Cold start: offline clustering on existing vault docs + historical RSS to pre-seed centroids
- Output: items with embedding and stable implicit_cluster ID

### Stage 1: Pre-filter (REWRITE from current filter.py)
- **Rule layer (zero cost):** domain whitelist check, content < 200 chars, zero keyword overlap with domains
- **LLM binary classification:** only items passing rules. Prompt: domains + title + first 300 chars. Output: 0 (skip) or 1 (continue). Not a score.
- Cut ~50% before LLM is called

### Stage 2: Analyze (ENHANCE from current analyze.py)
- **Call 1 (t=0.3):** Critical analysis — title_cn, summary, key_points, implications, confidence
- **Call 2 (t=0.1):** Structure extraction — entities[{name, type, mention_positions}], prediction{statement, deadline, outcome_var}|null
- Split for reliability: different cognitive tasks, different temperatures. Lower JSON parse failure rate.

### Stage 3: Post-filter (NEW)
- exploit_score: LLM relevance scoring 0-10, normalized to 0-1
- Surprise score deferred to v1.1
- Sort → top N proceed to Synthesize

### Stage 4: Synthesize (REWRITE from current synthesize.py)
- Density peak clustering on embedding space (not LLM clustering)
- Minimum 15 items to cluster; below threshold → lightweight report only
- One representative per near-duplicate cluster_id
- LLM explains each cluster: why these items belong together, theme title, cross-cluster connections via vector cosine angles (no hard relationship labels)

### Stage 5: Prediction Backtester (NEW, triggered)
- On each run: query predictions WHERE deadline <= today AND backtest_result IS NULL
- Structurable predictions → verify via external data sources
- Non-structurable predictions → generate observable signals for user to evaluate
- Update conclusion confidence based on backtest results
- Record score: correct / incorrect / partially_correct / unverifiable

### Stage 6: Output (REPLACE write.py)
- All data persisted in PostgreSQL
- FastAPI serves read-only REST API
- Single-page web app consumes API

## Data Model

### Tables

**items** — Raw + enriched items
- `id TEXT PRIMARY KEY` (sha256 of url)
- `source TEXT, title TEXT, url TEXT, content TEXT, published_at TIMESTAMPTZ`
- `fingerprint TEXT` (simhash)
- `cluster_id TEXT` (near-duplicate cluster)
- `embedding vector(384)` (all-MiniLM-L6)
- `implicit_cluster INT` (streaming clustering tag)
- `analysis JSONB` ({title_cn, summary, key_points, implications, confidence})
- `entities JSONB` ([{name, type, mention_positions}]) — no cross-item resolution in v1
- `prediction JSONB` ({statement, deadline, outcome_var}) or null
- `exploit_score FLOAT`
- `status TEXT` (new → enriched → analyzed → scored → incorporated)
- `created_at TIMESTAMPTZ DEFAULT now()`
- Index: `USING hnsw (embedding vector_cosine_ops)`

**conclusions** — System beliefs
- `id UUID PRIMARY KEY`
- `statement TEXT, domain TEXT`
- `embedding vector(384)`
- `confidence FLOAT` (0-1)
- `user_confirmation TEXT` (null / 'confirmed' / 'challenged')
- `status TEXT DEFAULT 'active'` (active / weakened / overturned / merged)
- `created_at TIMESTAMPTZ DEFAULT now()`

**conclusion_versions** — Append-only history
- `id UUID PRIMARY KEY`
- `conclusion_id UUID REFERENCES conclusions(id)`
- `version INT, statement TEXT, confidence FLOAT`
- `change_description TEXT`
- `triggered_by JSONB` ([{item_id, ...}])
- `created_at TIMESTAMPTZ DEFAULT now()`

**predictions** — Verifiable predictions
- `id UUID PRIMARY KEY`
- `item_id TEXT REFERENCES items(id)`
- `statement TEXT, deadline DATE, outcome_var TEXT`
- `backtest_result TEXT` (null / correct / incorrect / partially_correct / unverifiable)
- `backtest_reason TEXT, backtest_at TIMESTAMPTZ`
- Index: `(deadline) WHERE backtest_result IS NULL`

**run_log** — Pipeline observability (kept from v1)
- `id SERIAL PRIMARY KEY`
- `run_id TEXT, stage TEXT, status TEXT, item_count INT, duration_ms INT`
- `error TEXT, created_at TIMESTAMPTZ DEFAULT now()`

### Removed from v1
- `feedback` table — replaced by prediction backtesting + user confirmation mechanism
- `entities` table and `item_entities` join table — deferred to v1.1

## API Design

Read-only REST API. Write operations happen in pipeline via direct PG access.

```
GET  /api/graph                    # Full knowledge graph (nodes + edges)
GET  /api/graph/conclusion/:id     # Conclusion detail + version history + supporting items
GET  /api/graph/search?q=          # Semantic search across items, entities (JSONB), conclusions

GET  /api/stream                   # Cognitive update stream (reverse chrono)
     ?after=2026-05-29             # Cursor pagination
     &type=all                     # all | prediction_result | conclusion_update | new_item

GET  /api/predictions              # Prediction scorecard
     ?status=pending|verified|all

GET  /api/timeline                 # Timeline data for graph time slider
     ?from=2026-01-01&to=2026-05-30

GET  /api/runs                     # Pipeline run history
GET  /api/runs/:id                 # Single run detail

POST /api/trigger                  # Manually trigger a pipeline run
```

All list endpoints: cursor pagination, default limit 50.

## Web UI

Single page, three sections:

### Top: Knowledge Graph (D3 force simulation)
- Nodes: concepts (circles), people/orgs (diamonds), conclusions (rounded rects)
- Edges: colored by vector cosine similarity (green = close, red = distant)
- Node size proportional to connected items count
- Time range slider filters nodes by creation date
- Click node → right drawer opens with full detail + version history
- Pan/zoom canvas

### Middle: Cognitive Update Stream
- Reverse chronological feed
- Entry types: conclusion_updated (red/green), new_conclusion (green), prediction_backtest (checkmark/cross), new_item (neutral)
- Each entry shows: what changed, what triggered it, timestamp
- Click entry → graph navigates to related node
- Filter by type

### Bottom: Prediction Scorecard (collapsible)
- Table: prediction, deadline, result, source count
- Filter: pending / verified / all
- Accuracy rate displayed as header metric

### Interaction Flow
1. User opens page → sees knowledge graph
2. Scrolls down → reads latest cognitive updates
3. Clicks an update → graph auto-navigates to relevant node, drawer opens
4. In drawer: reads conclusion, sees version history, marks confirmed/challenged
5. Dragging time slider → graph animates to show knowledge state at that time

## Technology Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Database | PostgreSQL + pgvector (HNSW) | Vector search, JSONB, version history, full-text search |
| Backend | FastAPI (Python) | Same stack as existing, async |
| Frontend | Vanilla HTML/JS + D3.js | Four-section single page, no build toolchain needed |
| Embeddings | all-MiniLM-L6-v2 (sentence-transformers) | Keep existing model |
| LLM | OpenAI-compatible (deepseek-chat) via existing client | Keep existing |
| Scheduling | cron (health check email) | Simplest thing that works |

## What Gets Removed

| v1 Module | Disposition |
|-----------|-------------|
| `filter.py` | Split into `prefilter.py` + `postfilter.py` |
| `write.py` | Deleted — output is now PG + Web |
| `db.py` (SQLite) | Rewritten for PostgreSQL |
| `notify.py` (Slack) | Rewritten for email health check |
| `hermes/__main__.py` status/run | Repurposed. `run` triggers pipeline, new `web` command starts server |
| `config.yaml` feedback section | Removed |
| `feedback` table | Removed |

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM JSON parse failures break pipeline | Split analyze into two calls with appropriate temperatures; parse failures are caught per-item and don't block the run |
| Streaming clustering instability early on | Cold-start with offline clustering on existing vault + historical RSS |
| Prediction backtester can't verify non-structurable claims | Generate observable signals instead of requiring binary verification |
| PostgreSQL adds operational complexity vs SQLite | Accept as cost of vector search + JSONB queries. Single instance, no replicas needed |
| User stops using it after a few weeks | Ben's insight: daily open habit matters more than features. Start with health check emails to stay in the loop |

## v1.1 Preview (for context only, not scope of this spec)

- Surprise score (exploration track in post-filter)
- Entity resolution (cross-item entity merging into entities table)
- Blindspot scanning (hyper-sphere coverage gap detection)
- Additional information sources (newsletters, Twitter lists, YouTube)

---

## Deliverables

```
hermes/
├── hermes/
│   ├── __main__.py              # CLI: run, status, web commands
│   ├── config.py                 # Extended config
│   ├── db.py                     # PostgreSQL + pgvector
│   ├── health.py                 # Weekly email health check
│   ├── ingestors/
│   │   ├── rss.py                # Keep, minimal changes
│   │   └── obsidian.py           # NEW: read vault markdown files
│   ├── pipeline/
│   │   ├── run.py                # REWRITE: 6-stage orchestrator
│   │   ├── enrich.py             # NEW: embedding + streaming clustering
│   │   ├── dedup.py              # Keep
│   │   ├── prefilter.py          # REWRITE: rules + LLM binary
│   │   ├── analyze.py            # REWRITE: two-call analysis + prediction extraction
│   │   ├── postfilter.py         # NEW: exploit scoring
│   │   ├── synthesize.py         # REWRITE: density peak clustering → LLM explain
│   │   └── backtest.py           # NEW: triggered prediction backtesting
│   ├── web/
│   │   ├── app.py                # NEW: FastAPI application
│   │   ├── templates/
│   │   │   └── index.html        # Single page layout
│   │   └── static/
│   │       └── app.js            # D3 graph + stream rendering
│   ├── notify.py                 # REWRITE: email health check
│   └── embeddings.py             # Keep, add streaming clustering methods
├── migrations/
│   └── 001_init.sql              # PostgreSQL schema
├── tests/                        # Rewrite for new modules
├── config.yaml                   # Extended fields
└── pyproject.toml                # Add fastapi, uvicorn, psycopg2, pgvector
```
