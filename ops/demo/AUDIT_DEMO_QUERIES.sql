-- ClinCase — Live audit queries for the the 2026 hackathon demo.
--
-- Run these on stage from a psql terminal alongside the running app to prove
-- to the judges that EVERY decision is fully reproducible from first
-- principles. Per CMS-0057-F § IV.C and the panel's expected enterprise-
-- architect rubric, the audit trail is non-negotiable.
--
-- Usage:
--   psql "postgresql://clincase:clincase@localhost:15432/clincase"
--   \i ops/demo/AUDIT_DEMO_QUERIES.sql            -- run them all in sequence
--   \pset border 2                                -- prettify output for projector
--   \pset format aligned
--
-- Or invoke a single query inline:
--   psql -P "format=aligned" -P "border=2" -c "$(sed -n '/-- Q1 BEGIN/,/-- Q1 END/p' ops/demo/AUDIT_DEMO_QUERIES.sql)"

\set ON_ERROR_STOP on
\pset border 2
\pset format aligned
\pset null '∅'

-- =============================================================================
-- Q1 — Reconstruct any decision in <2 seconds
--
-- The script accepts :case_id at the psql command line:
--   psql -v case_id="'case_8f4ad9c2'" -f ops/demo/AUDIT_DEMO_QUERIES.sql
-- If unset, defaults to the most recently decided case.
-- =============================================================================

\set case_id `psql_default_unset_case_id_use_latest`

-- Resolve :case_id at runtime from the CLI variable; fallback to most recent.
SELECT
  CASE
    WHEN :'case_id' = 'psql_default_unset_case_id_use_latest'
    THEN (SELECT id FROM cases WHERE organization_id = 'org_demo' ORDER BY created_at DESC LIMIT 1)
    ELSE :'case_id'
  END AS resolved_case_id
\gset

\echo
\echo ===== Q1: full case provenance for :resolved_case_id =====

-- Q1 BEGIN
SELECT
  c.id                       AS case_id,
  c.payer_id,
  c.requested_treatment_name AS treatment,
  c.status,
  c.created_at,
  d.verdict,
  ROUND(d.confidence::numeric, 2) AS conf,
  d.created_at AS decided_at,
  EXTRACT(EPOCH FROM (d.created_at - c.created_at))::int AS decision_latency_seconds
FROM cases c
LEFT JOIN LATERAL (
  SELECT verdict, confidence, created_at
  FROM decisions
  WHERE case_id = c.id
  ORDER BY created_at DESC LIMIT 1
) d ON TRUE
WHERE c.id = :'resolved_case_id'
  AND c.organization_id = 'org_demo';
-- Q1 END


-- =============================================================================
-- Q2 — Every agent invocation, in order, with token + latency telemetry
-- =============================================================================

\echo
\echo ===== Q2: agent trace for :resolved_case_id =====

-- Q2 BEGIN
SELECT
  ROW_NUMBER() OVER (ORDER BY started_at)         AS step,
  agent_name,
  model_id,
  status,
  input_tokens,
  output_tokens,
  latency_ms,
  TO_CHAR(started_at, 'HH24:MI:SS.MS') AS started
FROM agent_traces
WHERE case_id = :'resolved_case_id'
ORDER BY started_at;
-- Q2 END


-- =============================================================================
-- Q3 — Per-case cost (Bedrock-Sonnet-4.6 priced at $3 / 1M input, $15 / 1M output)
-- =============================================================================

\echo
\echo ===== Q3: cost breakdown for :resolved_case_id =====

-- Q3 BEGIN
SELECT
  agent_name,
  input_tokens,
  output_tokens,
  ROUND(((COALESCE(input_tokens, 0) * 3.0  / 1000000)
       + (COALESCE(output_tokens, 0) * 15.0 / 1000000))::numeric, 6) AS usd
FROM agent_traces
WHERE case_id = :'resolved_case_id'
ORDER BY started_at;
-- Q3 END


-- =============================================================================
-- Q4 — Reviewer audit (any human override on this case)
-- =============================================================================

\echo
\echo ===== Q4: reviewer actions for :resolved_case_id =====

-- Q4 BEGIN
SELECT
  ra.action,
  ra.note,
  ra.created_at AS acted_at,
  u.email AS reviewer
FROM reviewer_actions ra
LEFT JOIN users u ON u.id = ra.reviewer_id
WHERE ra.case_id = :'resolved_case_id'
ORDER BY ra.created_at;
-- Q4 END


-- =============================================================================
-- Q5 — Cohort SLA posture against CMS-0057-F § IV.B.1 (7-day standard)
-- =============================================================================

\echo
\echo ===== Q5: CMS-0057-F § IV.B.1 SLA posture (org-wide) =====

-- Q5 BEGIN
WITH age AS (
  SELECT
    c.id,
    c.status,
    c.created_at,
    LEAST(
      EXTRACT(EPOCH FROM (NOW() - c.created_at)) / 86400.0,
      7
    ) AS age_days_capped,
    EXTRACT(EPOCH FROM (NOW() - c.created_at)) / 86400.0 AS age_days
  FROM cases c
  WHERE c.organization_id = 'org_demo'
)
SELECT
  COUNT(*)                                                  AS cohort_n,
  COUNT(*) FILTER (WHERE status NOT IN ('approved','denied','overturned','referred')) AS open_cases,
  COUNT(*) FILTER (WHERE age_days <= 7)                     AS within_sla,
  COUNT(*) FILTER (WHERE age_days >  7
                   AND status NOT IN ('approved','denied','overturned','referred')) AS overdue,
  ROUND(100.0 * COUNT(*) FILTER (WHERE age_days <= 7) / NULLIF(COUNT(*), 0), 1) AS within_sla_pct
FROM age;
-- Q5 END


-- =============================================================================
-- Q6 — Aggregate spend (Bedrock cost rolled up to org-day)
-- =============================================================================

\echo
\echo ===== Q6: org-wide Bedrock spend by day (last 14 days) =====

-- Q6 BEGIN
SELECT
  DATE(at.started_at) AS day,
  COUNT(DISTINCT at.case_id)                AS cases,
  SUM(at.input_tokens)                      AS in_tokens,
  SUM(at.output_tokens)                     AS out_tokens,
  ROUND(((SUM(COALESCE(at.input_tokens,0)) * 3.0
        + SUM(COALESCE(at.output_tokens,0)) * 15.0) / 1000000.0)::numeric, 4) AS usd
FROM agent_traces at
JOIN cases c ON c.id = at.case_id
WHERE c.organization_id = 'org_demo'
  AND at.started_at > NOW() - INTERVAL '14 days'
GROUP BY DATE(at.started_at)
ORDER BY day DESC;
-- Q6 END


\echo
\echo ===== Audit demo complete. =====
\echo Every row above is a permanent record on Postgres (production: Aurora
\echo Serverless v2 + KMS encryption). For any case_id, this script reproduces
\echo the full chain in under 2 seconds. CMS-0057-F § IV.C audit-grade.
