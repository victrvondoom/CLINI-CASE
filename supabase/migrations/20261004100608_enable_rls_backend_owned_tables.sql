-- Restore remote-applied migration 20261004100608.
-- These tables previously existed only after backend lifespan bootstraps.
-- Include their existing idempotent definitions so an empty preview database
-- can replay this migration before enabling RLS. Already-applied databases
-- retain this version in their history and do not rerun it.
SET search_path = public, extensions;

-- Existing backend schema: app/events/outbox.py
CREATE TABLE IF NOT EXISTS event_outbox (
    id              BIGSERIAL PRIMARY KEY,
    event_id        UUID UNIQUE NOT NULL,
    event_type      TEXT NOT NULL,
    event_version   TEXT NOT NULL DEFAULT 'v1',
    organization_id TEXT NOT NULL,
    aggregate_type  TEXT NOT NULL,
    aggregate_id    TEXT NOT NULL,
    payload_json    JSONB NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at    TIMESTAMPTZ,
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    trace_id        TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_outbox_pending
    ON event_outbox (occurred_at)
    WHERE published_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_event_outbox_org_type
    ON event_outbox (organization_id, event_type);
CREATE INDEX IF NOT EXISTS idx_event_outbox_aggregate
    ON event_outbox (aggregate_type, aggregate_id);

-- Existing backend schema: app/saga.py
CREATE TABLE IF NOT EXISTS case_sagas (
    saga_id          TEXT PRIMARY KEY,
    case_id          TEXT NOT NULL,
    organization_id  TEXT NOT NULL,
    saga_type        TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN
                       ('pending','running','completed','failed','compensated')),
    steps            JSONB NOT NULL DEFAULT '[]'::JSONB,
    error            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_case_sagas_case        ON case_sagas (case_id);
CREATE INDEX IF NOT EXISTS idx_case_sagas_org_status  ON case_sagas (organization_id, status);
CREATE INDEX IF NOT EXISTS idx_case_sagas_status      ON case_sagas (status) WHERE status IN ('pending','running','failed');

-- Existing backend schema: app/events/dlq.py
CREATE TABLE IF NOT EXISTS event_outbox_dlq (
    event_id          TEXT PRIMARY KEY,
    organization_id   TEXT NOT NULL,
    event_type        TEXT NOT NULL,
    case_id           TEXT,
    payload           JSONB NOT NULL,
    attempts          INTEGER NOT NULL,
    last_error        TEXT,
    moved_to_dlq_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    original_created_at TIMESTAMPTZ NOT NULL,
    replay_count      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_dlq_org           ON event_outbox_dlq (organization_id);
CREATE INDEX IF NOT EXISTS idx_dlq_event_type    ON event_outbox_dlq (event_type);
CREATE INDEX IF NOT EXISTS idx_dlq_moved         ON event_outbox_dlq (moved_to_dlq_at);

-- Existing backend schema: app/security/breach_detector.py
CREATE TABLE IF NOT EXISTS security_anomalies (
    id                 BIGSERIAL PRIMARY KEY,
    detected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    organization_id    TEXT,
    signal             TEXT NOT NULL,
    severity           TEXT NOT NULL CHECK (severity IN ('info','warn','high','critical')),
    payload            JSONB NOT NULL,
    sns_published      BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_secanom_detected ON security_anomalies (detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_secanom_signal   ON security_anomalies (signal);
CREATE INDEX IF NOT EXISTS idx_secanom_org      ON security_anomalies (organization_id);

-- Existing backend schema: app/api/idempotency_middleware.py
CREATE TABLE IF NOT EXISTS idempotency_keys (
    organization_id   TEXT NOT NULL,
    key               TEXT NOT NULL,
    method            TEXT NOT NULL,
    path              TEXT NOT NULL,
    request_hash      TEXT NOT NULL,
    response_status   INTEGER,
    response_body     BYTEA,
    response_headers  JSONB,
    in_flight         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ,
    expires_at        TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (organization_id, key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_keys (expires_at);

-- Existing backend schema: app/api/fhir_bulk.py
CREATE TABLE IF NOT EXISTS fhir_bulk_jobs (
    job_id            TEXT PRIMARY KEY,
    organization_id   TEXT NOT NULL,
    requested_by      TEXT NOT NULL,
    resource_types    TEXT[] NOT NULL,
    since             TIMESTAMPTZ,
    status            TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','cancelled')),
    request_url       TEXT,
    output_manifest   JSONB,
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_fhir_bulk_org_status ON fhir_bulk_jobs (organization_id, status);

-- Existing backend schema: app/privacy/erasure.py
CREATE TABLE IF NOT EXISTS subject_redactions (
    redaction_id     TEXT PRIMARY KEY,
    organization_id  TEXT NOT NULL,
    subject_token    TEXT NOT NULL,
    subject_initials TEXT,
    reason           TEXT NOT NULL,
    requested_by     TEXT NOT NULL,
    legal_basis      TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN
                       ('soft_deleted','hard_delete_scheduled','hard_deleted','rejected')),
    soft_deleted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hard_delete_after TIMESTAMPTZ NOT NULL,
    hard_deleted_at  TIMESTAMPTZ,
    rejection_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_redactions_org    ON subject_redactions (organization_id);
CREATE INDEX IF NOT EXISTS idx_redactions_status ON subject_redactions (status);
CREATE INDEX IF NOT EXISTS idx_redactions_token  ON subject_redactions (subject_token);

-- Existing backend schema: app/privacy/tokenization.py
CREATE TABLE IF NOT EXISTS phi_vault (
    organization_id  TEXT NOT NULL,
    token            TEXT NOT NULL,
    value_kind       TEXT NOT NULL CHECK (value_kind IN ('mrn','ssn','dob','npi','dea','custom')),
    real_value_hmac  TEXT NOT NULL,
    encrypted_value  BYTEA NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ,
    access_count     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (organization_id, token)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_phivault_value_lookup
    ON phi_vault (organization_id, value_kind, real_value_hmac);

CREATE TABLE IF NOT EXISTS phi_vault_access_log (
    id                BIGSERIAL PRIMARY KEY,
    organization_id   TEXT NOT NULL,
    token             TEXT NOT NULL,
    accessor_id       TEXT NOT NULL,
    operation         TEXT NOT NULL CHECK (operation IN ('tokenize','detokenize')),
    accessed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    purpose           TEXT
);
CREATE INDEX IF NOT EXISTS idx_phivault_access_log_org_time
    ON phi_vault_access_log (organization_id, accessed_at DESC);

-- Existing backend schema: app/prompts_versioning.py
CREATE TABLE IF NOT EXISTS prompts (
    agent_name        TEXT NOT NULL,
    version           TEXT NOT NULL,
    body              TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('draft','shadow','active','retired')),
    description       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at      TIMESTAMPTZ,
    retired_at        TIMESTAMPTZ,
    PRIMARY KEY (agent_name, version)
);
CREATE INDEX IF NOT EXISTS idx_prompts_active ON prompts (agent_name) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS prompt_assignments (
    organization_id  TEXT NOT NULL,
    agent_name       TEXT NOT NULL,
    version          TEXT NOT NULL,
    assigned_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (organization_id, agent_name)
);

CREATE TABLE IF NOT EXISTS prompt_traffic_splits (
    agent_name       TEXT NOT NULL,
    version          TEXT NOT NULL,
    weight_percent   NUMERIC(5,2) NOT NULL CHECK (weight_percent >= 0 AND weight_percent <= 100),
    PRIMARY KEY (agent_name, version)
);

-- Existing backend schema: app/quotas.py
CREATE TABLE IF NOT EXISTS org_quotas (
    organization_id        TEXT        PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    daily_case_limit       INTEGER     NOT NULL DEFAULT 1000  CHECK (daily_case_limit >= 0),
    monthly_case_limit     INTEGER     NOT NULL DEFAULT 30000 CHECK (monthly_case_limit >= 0),
    current_day            DATE        NOT NULL DEFAULT CURRENT_DATE,
    current_day_count      INTEGER     NOT NULL DEFAULT 0     CHECK (current_day_count >= 0),
    current_month          DATE        NOT NULL DEFAULT date_trunc('month', CURRENT_DATE)::date,
    current_month_count    INTEGER     NOT NULL DEFAULT 0     CHECK (current_month_count >= 0),
    -- Per-tenant data residency — drives RDS cluster + S3 bucket region selection.
    -- Defaults to ap-south-1; flip per customer's regulatory requirement
    -- (HDS for FR healthcare, DPDP for IN, HIPAA region preference for US payers).
    data_region            TEXT        NOT NULL DEFAULT 'ap-south-1',
    -- Pricing / SLA tier — Bronze / Silver / Gold drives WAF rate-limit + Bedrock
    -- model allowlist + on-call escalation tier.
    tier                   TEXT        NOT NULL DEFAULT 'silver' CHECK (tier IN ('bronze','silver','gold')),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_org_quotas_day    ON org_quotas (current_day);
CREATE INDEX IF NOT EXISTS idx_org_quotas_region ON org_quotas (data_region);
CREATE INDEX IF NOT EXISTS idx_org_quotas_tier   ON org_quotas (tier);

-- Idempotent ALTER (existing DBs predating data_region/tier columns)
ALTER TABLE org_quotas ADD COLUMN IF NOT EXISTS data_region TEXT NOT NULL DEFAULT 'ap-south-1';
ALTER TABLE org_quotas ADD COLUMN IF NOT EXISTS tier        TEXT NOT NULL DEFAULT 'silver';

-- Existing backend schema: app/agents/framework/cache.py
CREATE TABLE IF NOT EXISTS agent_response_cache (
    cache_key       TEXT        PRIMARY KEY,
    agent_name      TEXT        NOT NULL,
    organization_id TEXT        NOT NULL,
    output_json     JSONB       NOT NULL,
    model_id        TEXT,
    input_tokens    INTEGER     NOT NULL DEFAULT 0,
    output_tokens   INTEGER     NOT NULL DEFAULT 0,
    schema_version  TEXT        NOT NULL,
    hits            INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_arc_agent       ON agent_response_cache (agent_name);
CREATE INDEX IF NOT EXISTS idx_arc_expires     ON agent_response_cache (expires_at);
CREATE INDEX IF NOT EXISTS idx_arc_org         ON agent_response_cache (organization_id);

-- Existing backend schema: app/llm/gateway.py
CREATE TABLE IF NOT EXISTS llm_invocations (
    id              BIGSERIAL PRIMARY KEY,
    invocation_id   UUID        NOT NULL,
    organization_id TEXT        NOT NULL,
    case_id         TEXT,
    agent_name      TEXT,
    model_id        TEXT        NOT NULL,
    input_tokens    INTEGER     NOT NULL DEFAULT 0,
    output_tokens   INTEGER     NOT NULL DEFAULT 0,
    cost_usd        REAL        NOT NULL DEFAULT 0.0,
    latency_ms      INTEGER,
    status          TEXT        NOT NULL DEFAULT 'ok',
    error_text      TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);
ALTER TABLE llm_invocations ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE llm_invocations ADD COLUMN IF NOT EXISTS case_intelligence_id TEXT;
ALTER TABLE llm_invocations ADD COLUMN IF NOT EXISTS trace_id TEXT;
CREATE INDEX IF NOT EXISTS idx_llmi_run ON llm_invocations (run_id);
CREATE INDEX IF NOT EXISTS idx_llmi_org_started ON llm_invocations (organization_id, started_at);
CREATE INDEX IF NOT EXISTS idx_llmi_case        ON llm_invocations (case_id);

CREATE TABLE IF NOT EXISTS tenant_policies (
    organization_id        TEXT        PRIMARY KEY,
    allowed_model_ids      JSONB       NOT NULL DEFAULT '[]'::jsonb,
    daily_input_token_cap  INTEGER     NOT NULL DEFAULT 50000000,
    daily_output_token_cap INTEGER     NOT NULL DEFAULT 10000000,
    daily_usd_cap          REAL        NOT NULL DEFAULT 1000.0,
    bedrock_guardrail_id   TEXT,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Existing backend schema: app/oncotwin/store.py
CREATE TABLE IF NOT EXISTS oncotwin_audit (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    seq             BIGINT NOT NULL,
    kind            TEXT NOT NULL,
    patient_id      TEXT,
    actor           TEXT,
    created_at      TIMESTAMPTZ NOT NULL,
    payload         JSONB NOT NULL,
    prev_hash       TEXT NOT NULL,
    hash            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oncotwin_audit_org ON oncotwin_audit(organization_id, created_at);
CREATE INDEX IF NOT EXISTS idx_oncotwin_audit_patient ON oncotwin_audit(organization_id, patient_id);

-- Existing backend schema: app/aquahealth/store.py
CREATE TABLE IF NOT EXISTS aquahealth_waterbodies (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL,
    locality        TEXT,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    is_demo         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL,
    payload         JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_aqua_wb_org
    ON aquahealth_waterbodies(organization_id, created_at);

CREATE TABLE IF NOT EXISTS aquahealth_observations (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    reference       TEXT NOT NULL,
    waterbody_id    TEXT NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    status          TEXT,
    review_status   TEXT NOT NULL,
    source          TEXT NOT NULL,
    is_demo         BOOLEAN NOT NULL DEFAULT FALSE,
    payload         JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_aqua_obs_org
    ON aquahealth_observations(organization_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_aqua_obs_wb
    ON aquahealth_observations(organization_id, waterbody_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_aqua_obs_review
    ON aquahealth_observations(organization_id, review_status);

-- Existing backend schema: app/onehealth/repository.py
CREATE TABLE IF NOT EXISTS onehealth_exposures (
 organization_id TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL,
 payload JSONB NOT NULL, PRIMARY KEY (organization_id, id)
);

-- Existing backend schema: app/interop/repository.py
CREATE TABLE IF NOT EXISTS interop_jobs (
 organization_id TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL,
 payload JSONB NOT NULL, PRIMARY KEY (organization_id,id));
CREATE TABLE IF NOT EXISTS interop_artifacts (
 organization_id TEXT NOT NULL, job_id TEXT NOT NULL, kind TEXT NOT NULL,
 payload JSONB NOT NULL, PRIMARY KEY (organization_id,job_id,kind));

-- Original recorded security statements (unchanged).
-- The ClinCase backend connects as the table owner (postgres), which bypasses RLS.
-- Enabling RLS with no policies closes the Supabase Data API (anon/authenticated) path only.
ALTER TABLE public.event_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_sagas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.event_outbox_dlq ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.security_anomalies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.idempotency_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fhir_bulk_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subject_redactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.phi_vault ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.phi_vault_access_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompt_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompt_traffic_splits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.org_quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_response_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.llm_invocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.oncotwin_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.aquahealth_waterbodies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.aquahealth_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.onehealth_exposures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interop_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interop_artifacts ENABLE ROW LEVEL SECURITY;
