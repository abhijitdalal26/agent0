CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS model_profiles (
    name text PRIMARY KEY,
    provider text NOT NULL,
    model text NOT NULL,
    capability text NOT NULL,
    tags text[] NOT NULL DEFAULT '{}',
    cost jsonb NOT NULL DEFAULT '{}',
    settings jsonb NOT NULL DEFAULT '{}',
    key_env text NOT NULL,
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS agents (
    name text PRIMARY KEY,
    instructions_md text NOT NULL,
    model_profile text,
    tools jsonb NOT NULL DEFAULT '[]',
    policy jsonb NOT NULL DEFAULT '{}',
    version int NOT NULL DEFAULT 1,
    definition jsonb,
    versions jsonb NOT NULL DEFAULT '[]',
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
    id text PRIMARY KEY,
    title text NOT NULL,
    prompt text NOT NULL,
    source text NOT NULL,
    agent text NOT NULL,
    status text NOT NULL,
    notify_level text NOT NULL,
    budget jsonb NOT NULL DEFAULT '{}',
    chat_id text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runs (
    id text PRIMARY KEY,
    task_id text NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    attempt int NOT NULL,
    status text NOT NULL,
    agent text NOT NULL,
    model_profile text,
    current_step text,
    temporal_workflow_id text,
    tokens_in int NOT NULL DEFAULT 0,
    tokens_out int NOT NULL DEFAULT 0,
    cost_usd numeric(12, 6) NOT NULL DEFAULT 0,
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz
);
CREATE INDEX IF NOT EXISTS runs_task_idx ON runs (task_id);
CREATE INDEX IF NOT EXISTS runs_status_idx ON runs (status);

CREATE TABLE IF NOT EXISTS task_specs (
    task_id text PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    goal text NOT NULL,
    steps jsonb NOT NULL DEFAULT '[]',
    criteria jsonb NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS events (
    id text PRIMARY KEY,
    run_id text NOT NULL,
    seq int NOT NULL,
    type text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    prev_hash text,
    hash text,
    UNIQUE (run_id, seq)
);
CREATE INDEX IF NOT EXISTS events_created_idx ON events (created_at);

CREATE TABLE IF NOT EXISTS verdicts (
    id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    check_id text NOT NULL,
    type text NOT NULL,
    status text NOT NULL,
    evidence text NOT NULL DEFAULT '',
    score double precision,
    cost_usd numeric(12, 6) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS approvals (
    id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    question text NOT NULL,
    options jsonb NOT NULL DEFAULT '["approve","reject"]',
    status text NOT NULL DEFAULT 'pending',
    decided_by text,
    decided_at timestamptz,
    note text
);

CREATE TABLE IF NOT EXISTS artifacts (
    id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    path text NOT NULL,
    kind text NOT NULL,
    size bigint NOT NULL DEFAULT 0,
    storage_url text
);

CREATE TABLE IF NOT EXISTS usage (
    id bigserial PRIMARY KEY,
    run_id text,
    profile text NOT NULL,
    provider text NOT NULL,
    model text NOT NULL,
    capability text NOT NULL,
    input_units int NOT NULL DEFAULT 0,
    output_units int NOT NULL DEFAULT 0,
    cost_usd numeric(12, 6) NOT NULL DEFAULT 0,
    latency_ms int NOT NULL DEFAULT 0,
    ok boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS usage_created_idx ON usage (created_at);

CREATE TABLE IF NOT EXISTS memory_docs (
    id text PRIMARY KEY,
    scope text NOT NULL,
    scope_id text,
    path text NOT NULL,
    content text NOT NULL,
    revision int NOT NULL DEFAULT 1,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS facts (
    id text PRIMARY KEY,
    scope text NOT NULL,
    scope_id text,
    content text NOT NULL,
    source_id text,
    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_to timestamptz,
    superseded_by text,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    embedding vector(768)
);
CREATE INDEX IF NOT EXISTS facts_tsv_idx ON facts USING gin (tsv);

CREATE TABLE IF NOT EXISTS run_summaries (
    run_id text PRIMARY KEY,
    summary text NOT NULL,
    outcome text NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', summary)) STORED,
    embedding vector(768),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS run_summaries_tsv_idx ON run_summaries USING gin (tsv);

CREATE TABLE IF NOT EXISTS knowledge_sources (
    name text PRIMARY KEY,
    kind text NOT NULL,
    config jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id text PRIMARY KEY,
    source text NOT NULL REFERENCES knowledge_sources(name) ON DELETE CASCADE,
    content text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}',
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    embedding vector(768)
);
CREATE INDEX IF NOT EXISTS knowledge_chunks_tsv_idx ON knowledge_chunks USING gin (tsv);

CREATE TABLE IF NOT EXISTS extensions (
    id text PRIMARY KEY,
    kind text NOT NULL,
    name text NOT NULL,
    description text NOT NULL DEFAULT '',
    enabled boolean NOT NULL DEFAULT true,
    config jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS schedules (
    id text PRIMARY KEY,
    agent text NOT NULL,
    cron text NOT NULL,
    prompt text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    last_run_at timestamptz,
    next_run_at timestamptz
);

CREATE TABLE IF NOT EXISTS secrets (
    name text PRIMARY KEY,
    ciphertext bytea NOT NULL,
    last4 text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text
);

-- Columns added after the table first shipped; CREATE IF NOT EXISTS won't alter it.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS definition jsonb;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS versions jsonb NOT NULL DEFAULT '[]';
ALTER TABLE schedules ADD COLUMN IF NOT EXISTS next_run_at timestamptz;
ALTER TABLE events ADD COLUMN IF NOT EXISTS prev_hash text;
ALTER TABLE events ADD COLUMN IF NOT EXISTS hash text;
