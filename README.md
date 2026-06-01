# Hermes

Personal intelligence monitoring system. Continuously ingests RSS feeds, analyzes articles with LLMs, and builds a versioned knowledge graph with predictions and backtesting.

## Architecture

```
RSS → Ingest → Enrich → Dedup → Assess → Surprise → Synthesize → Backtest
                                    ↓           ↓            ↓
                              predictions   knowledge    verified
                                            graph       predictions
```

| Stage | What it does |
|---|---|
| **Ingest** | Fetches RSS feeds, stores raw articles in PostgreSQL |
| **Enrich** | Computes 384-dim embeddings via `all-MiniLM-L6-v2`, assigns to streaming clusters |
| **Dedup** | Removes near-duplicates via SimHash + URL dedup |
| **Assess** | LLM judges relevance, extracts entities, scores exploit potential, optionally proposes new domains |
| **Surprise** | Measures how semantically different an item is from existing conclusions in the same domain |
| **Synthesize** | Groups assessed items by semantic density, generates/updates conclusions with counter-arguments |
| **Backtest** | Evaluates past predictions against current evidence |

Each conclusion is **versioned**. When new evidence shifts confidence, a new version is created with a change description rather than overwriting history.

## Setup

**Prerequisites:** Python 3.12+, PostgreSQL with [pgvector](https://github.com/pgvector/pgvector)

```bash
# Clone and set up venv
git clone <repo-url> && cd hermes
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Create config
mkdir -p ~/.hermes
cp config.yaml ~/.hermes/config.yaml
# Edit DB URL, API keys, domains to match your environment

# Run migrations
for f in migrations/*.sql; do
  psql $DATABASE_URL -f "$f"
done
```

**Required environment variables:**
- `DEEPSEEK_API_KEY` — LLM API key (config references `${DEEPSEEK_API_KEY}`)
- `HERMES_EMAIL_PASSWORD` — SMTP password for health checks (optional)

## Usage

```
hermes run              # Full pipeline
hermes cron             # Pipeline without summary output (for cron)
hermes status           # Show last run summary
hermes web --port 8080  # Start web server
hermes audit -n 5       # Manual audit of LLM analysis quality
hermes test-prompts     # Prompt regression tests against annotated fixtures
hermes health           # Send weekly health check email
```

## Web UI

```
http://localhost:8080/
```

- **Knowledge Graph** — domain-grouped force layout. Each domain occupies a distinct region. Cross-domain edges show semantic bridges. Click a node to open the evidence drawer with supporting articles, confidence breakdown, counter-arguments, and confirm/challenge buttons.
- **Surprise** — articles semantically distant from existing conclusions in their domain.
- **Predictions** — pending predictions with countdown timers, verified predictions with results.
- **Activity** — chronological pipeline run log.

## Configuration

See `config.yaml` for the full schema. Key sections:

- `sources.rss` — RSS feeds with `enabled` flag
- `llm` — model provider (DeepSeek Chat by default)
- `domains` — list of intelligence domains for classification
- `database.url` — PostgreSQL connection string
- `scoring` — exploit threshold, cluster distance
- `email` / `notify` — SMTP and Slack webhook settings

Config values can reference environment variables with `${VAR_NAME}` syntax.

## Development

```bash
# Run tests
pytest

# Run specific test file
pytest tests/test_assess.py

# Run prompt regression tests
hermes test-prompts -n 5 --threshold 4
```

**Migrations** are in `migrations/` as numbered SQL files. They're applied idempotently (each uses `IF NOT EXISTS`).

## Database

PostgreSQL with pgvector extension. Core tables:

- `items` — ingested articles with embeddings, analysis, status
- `conclusions` — synthesized knowledge with confidence, domain, embedding
- `conclusion_versions` — versioned history with change descriptions
- `predictions` — forecasted statements with deadlines and backtest results
- `run_log` — pipeline stage timing and status
