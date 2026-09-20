-- ClinCase database schema
-- Applied at Postgres container init (mounted to /docker-entrypoint-initdb.d/)
-- and by `make db.init`. Idempotent — safe to run on a live DB.

CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- organizations  — tenant boundary (one row per provider org / health system)
-- =============================================================================
CREATE TABLE IF NOT EXISTS organizations (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    slug         TEXT NOT NULL UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default tenant for backfilled / demo data
INSERT INTO organizations (id, name, slug)
VALUES ('org_demo', 'Aerofyta Health Sciences', 'aerofyta')
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- users  — authenticated humans within an organization
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL DEFAULT 'coordinator'
                    CHECK (role IN ('coordinator','reviewer','admin')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_org   ON users(organization_id);

-- =============================================================================
-- cases  — one row per prior-authorisation request
-- =============================================================================
CREATE TABLE IF NOT EXISTS cases (
    id                       TEXT PRIMARY KEY,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    organization_id          TEXT NOT NULL DEFAULT 'org_demo',
    created_by_user_id       TEXT,
    payer_id                 TEXT NOT NULL,
    patient_initials         TEXT NOT NULL,
    requested_treatment_name TEXT NOT NULL,
    requested_j_code         TEXT,
    fhir_bundle              JSONB NOT NULL,
    physician_note           TEXT,
    status                   TEXT NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending','running','approved','denied','referred','appealed','overturned'))
);

-- Idempotent ALTER (existing DBs that pre-date organizations)
ALTER TABLE cases ADD COLUMN IF NOT EXISTS organization_id TEXT NOT NULL DEFAULT 'org_demo';
ALTER TABLE cases ADD COLUMN IF NOT EXISTS created_by_user_id TEXT;

-- Wire FKs only after both tables exist (idempotent)
DO $$ BEGIN
    BEGIN
        ALTER TABLE cases ADD CONSTRAINT cases_organization_id_fkey
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END;
    BEGIN
        ALTER TABLE cases ADD CONSTRAINT cases_created_by_user_id_fkey
            FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END;
END $$;

CREATE INDEX IF NOT EXISTS idx_cases_payer    ON cases(payer_id);
CREATE INDEX IF NOT EXISTS idx_cases_status   ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_created  ON cases(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_org      ON cases(organization_id);

-- =============================================================================
-- agent_runs  — one row per agent invocation per case (the audit trail)
-- =============================================================================
CREATE TABLE IF NOT EXISTS agent_runs (
    id           BIGSERIAL PRIMARY KEY,
    case_id      TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    agent_name   TEXT NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL,
    finished_at  TIMESTAMPTZ,
    input_json   JSONB NOT NULL,
    output_json  JSONB,
    tool_calls   JSONB,
    latency_ms   INTEGER,
    error_text   TEXT,
    model_id     TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_case  ON agent_runs(case_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name);

-- =============================================================================
-- decisions  — final verdict per case (one row per case run)
-- =============================================================================
CREATE TABLE IF NOT EXISTS decisions (
    id             BIGSERIAL PRIMARY KEY,
    case_id        TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    verdict        TEXT NOT NULL CHECK (verdict IN ('APPROVE','DENY','REFER')),
    rationale      TEXT NOT NULL,
    citations_json JSONB NOT NULL,
    confidence     REAL NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_case ON decisions(case_id);

-- =============================================================================
-- appeals  — drafted appeal letters
-- =============================================================================
CREATE TABLE IF NOT EXISTS appeals (
    id                        BIGSERIAL PRIMARY KEY,
    case_id                   TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    appeal_body               TEXT NOT NULL,
    structured_arguments_json JSONB NOT NULL,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_appeals_case ON appeals(case_id);

-- =============================================================================
-- reviewer_actions  — human-in-the-loop overrides
-- =============================================================================
CREATE TABLE IF NOT EXISTS reviewer_actions (
    id           BIGSERIAL PRIMARY KEY,
    case_id      TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    reviewer_id  TEXT NOT NULL,
    action       TEXT NOT NULL CHECK (action IN ('approve','override_to_approve','override_to_deny','escalate','add_note')),
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviewer_actions_case ON reviewer_actions(case_id);

-- =============================================================================
-- policy_chunks  — RAG corpus (pgvector path; Bedrock KB path bypasses this)
-- =============================================================================
CREATE TABLE IF NOT EXISTS policy_chunks (
    id              BIGSERIAL PRIMARY KEY,
    payer_id        TEXT NOT NULL,
    policy_id       TEXT NOT NULL,
    policy_title    TEXT NOT NULL,
    section_heading TEXT,
    chunk_text      TEXT NOT NULL,
    page_number     INTEGER,
    source_url      TEXT,
    embedding       VECTOR(384) NOT NULL  -- sentence-transformers/all-MiniLM-L6-v2
);

CREATE INDEX IF NOT EXISTS idx_policy_chunks_payer ON policy_chunks(payer_id);
CREATE INDEX IF NOT EXISTS idx_policy_chunks_embedding
    ON policy_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
