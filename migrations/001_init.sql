-- Hermes v2 schema: PostgreSQL + pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Raw + enriched items
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    content TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    fingerprint TEXT,
    cluster_id TEXT,
    embedding vector(384),
    implicit_cluster INT,
    analysis JSONB,
    entities JSONB,
    prediction JSONB,
    exploit_score FLOAT,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_cluster ON items(cluster_id);
CREATE INDEX IF NOT EXISTS idx_items_implicit_cluster ON items(implicit_cluster);
CREATE INDEX IF NOT EXISTS idx_items_embedding ON items USING hnsw (embedding vector_cosine_ops);

-- System beliefs with version history
CREATE TABLE IF NOT EXISTS conclusions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statement TEXT NOT NULL,
    domain TEXT,
    embedding vector(384),
    confidence FLOAT DEFAULT 0.5,
    user_confirmation TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conclusion_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conclusion_id UUID NOT NULL REFERENCES conclusions(id),
    version INT NOT NULL,
    statement TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    change_description TEXT,
    triggered_by JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conclusion_versions_cid ON conclusion_versions(conclusion_id);

-- Verifiable predictions
CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id TEXT NOT NULL REFERENCES items(id),
    statement TEXT NOT NULL,
    deadline DATE NOT NULL,
    outcome_var TEXT,
    backtest_result TEXT,
    backtest_reason TEXT,
    backtest_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_predictions_deadline ON predictions(deadline) WHERE backtest_result IS NULL;

-- Pipeline observability
CREATE TABLE IF NOT EXISTS run_log (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    item_count INT DEFAULT 0,
    duration_ms INT DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_run_log_run_id ON run_log(run_id);
