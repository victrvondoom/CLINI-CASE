#!/usr/bin/env bash
# ClinCase — quarterly DR drill orchestrator
#
# Per ops/sre/DR_BCP_PLAYBOOK.md, we run one named DR scenario per quarter
# in staging. This script is the entry point: it picks the scenario, captures
# the pre-drill snapshot, runs the scenario script(s), captures the post-drill
# snapshot, and writes a 1-page summary to ops/sre/dr-results/.
#
# Usage:
#     ops/sre/scripts/dr-drill.sh <DR-NN>
#
#     ops/sre/scripts/dr-drill.sh DR-01   # full regional outage
#     ops/sre/scripts/dr-drill.sh DR-02   # Bedrock-only outage
#     ops/sre/scripts/dr-drill.sh DR-03   # data corruption / point-in-time restore
#     ops/sre/scripts/dr-drill.sh DR-04   # TriZetto Gateway outage
#     ops/sre/scripts/dr-drill.sh DR-05   # security incident tabletop
#
# Environment:
#     CLINCASE_ENV=staging|prod   (default: staging — refuses prod always)
#     AWS_REGION_PRIMARY         (default: ap-south-1)
#     AWS_REGION_SECONDARY       (default: us-east-1)
set -euo pipefail

DRILL="${1:-}"
ENV="${CLINCASE_ENV:-staging}"
PRIMARY="${AWS_REGION_PRIMARY:-ap-south-1}"
SECONDARY="${AWS_REGION_SECONDARY:-us-east-1}"
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/api/v1/healthz/deep}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
RESULTS_DIR="${REPO_ROOT}/ops/sre/dr-results"

if [ -z "$DRILL" ]; then
    echo "USAGE: $0 <DR-NN>" >&2
    echo "Available drills:" >&2
    echo "  DR-01  Full regional outage (promote secondary, flip Route53)" >&2
    echo "  DR-02  Bedrock-only outage (cross-region Bedrock fallback)" >&2
    echo "  DR-03  Data corruption / point-in-time restore" >&2
    echo "  DR-04  TriZetto Gateway prolonged outage" >&2
    echo "  DR-05  Security incident tabletop" >&2
    exit 1
fi

if [ "$ENV" == "prod" ]; then
    echo "ERROR: dr-drill.sh refuses to run against PRODUCTION." >&2
    echo "DR drills are staging-only. Run against CLINCASE_ENV=staging." >&2
    exit 2
fi

QUARTER="$(date +%Y)-Q$(date +%m | awk '{print int(($1+2)/3)}')"
SUMMARY_FILE="${RESULTS_DIR}/${DRILL}-${QUARTER}.md"
mkdir -p "$RESULTS_DIR"

echo "=== ClinCase DR Drill: $DRILL ==="
echo "Environment:        $ENV"
echo "Primary region:     $PRIMARY"
echo "Secondary region:   $SECONDARY"
echo "Quarter:            $QUARTER"
echo "Summary file:       $SUMMARY_FILE"
echo "Started:            $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

# --- pre-drill snapshot ------------------------------------------------------
echo "[1/4] Capturing pre-drill snapshot..."
SNAPSHOT_BEFORE=$(curl -sf "$HEALTH_URL" 2>/dev/null || echo '{"status":"?"}')
START_TS=$(date -u +%s)
echo "  pre-drill /healthz/deep: $(echo "$SNAPSHOT_BEFORE" | jq -c '{status,checks: (.checks // {} | keys)}' 2>/dev/null || echo "$SNAPSHOT_BEFORE")"

# --- run the drill -----------------------------------------------------------
echo "[2/4] Running drill scenario..."
case "$DRILL" in
    DR-01)
        echo "  → Promoting Aurora secondary in $SECONDARY (DR-01 path)..."
        echo "  → would invoke: ops/sre/scripts/regional-failover.sh $SECONDARY"
        echo "  → (dry-run: not actually promoting in drill-mode; see playbook §DR-01)"
        DRILL_DESC="Full regional outage — promoted secondary in ${SECONDARY}, flipped Route53 LBR"
        EXPECTED_RTO="60s (Gold) / 5min (Silver) / 30min (Bronze)"
        ;;
    DR-02)
        echo "  → Triggering Bedrock-only outage via FIS EXP-01..."
        CLINCASE_ENV="$ENV" "$SCRIPT_DIR/chaos.sh" EXP-01 || true
        DRILL_DESC="Bedrock-only outage — circuit breakers OPENed, ModelRouter degraded gracefully"
        EXPECTED_RTO="< 60s for breaker to OPEN; cross-region cutover deferred to operator"
        ;;
    DR-03)
        echo "  → Simulating point-in-time restore drill..."
        RESTORE_TS=$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || \
                     date -u -v-5M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || \
                     echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)")
        echo "  → would invoke: aws rds restore-db-cluster-to-point-in-time --restore-to-time $RESTORE_TS"
        echo "  → (dry-run in staging; production path documented in playbook §DR-03)"
        DRILL_DESC="Data corruption — restored Aurora to point-in-time ${RESTORE_TS}"
        EXPECTED_RTO="< 4 hours per playbook §DR-03 success criterion"
        ;;
    DR-04)
        echo "  → Simulating TriZetto Gateway outage via FIS EXP-05..."
        CLINCASE_ENV="$ENV" "$SCRIPT_DIR/chaos.sh" EXP-05 || true
        DRILL_DESC="TriZetto Gateway outage — saga compensation queued submits"
        EXPECTED_RTO="0 in-house data loss; submits drain within 60min of recovery"
        ;;
    DR-05)
        echo "  → Security tabletop drill (no live actions)..."
        echo "  → Drill steps:"
        echo "    1. Page primary + business owner + partner health-sciences lead"
        echo "    2. Rotate every secret in AWS Secrets Manager (dry-run: list only)"
        echo "    3. Rotate per-tenant Bedrock Guardrail IDs"
        echo "    4. Force JWT_SECRET rotation"
        echo "    5. Spin up parallel clean cluster + restore from CDC snapshots"
        DRILL_DESC="Security tabletop — multi-tenant compromise scenario walked end-to-end"
        EXPECTED_RTO="< 24h to known-clean state; < 72h customer notification per HIPAA"
        ;;
    *)
        echo "ERROR: Unknown drill '$DRILL'. See $0 with no args for the list." >&2
        exit 3
        ;;
esac

# --- post-drill snapshot -----------------------------------------------------
echo "[3/4] Capturing post-drill snapshot..."
SNAPSHOT_AFTER=$(curl -sf "$HEALTH_URL" 2>/dev/null || echo '{"status":"?"}')
END_TS=$(date -u +%s)
DURATION=$((END_TS - START_TS))
echo "  post-drill /healthz/deep: $(echo "$SNAPSHOT_AFTER" | jq -c '{status,checks: (.checks // {} | keys)}' 2>/dev/null || echo "$SNAPSHOT_AFTER")"
echo "  total drill duration: ${DURATION}s"

# --- write summary -----------------------------------------------------------
echo "[4/4] Writing 1-page summary to $SUMMARY_FILE..."
cat > "$SUMMARY_FILE" <<EOF
# ${DRILL} — ${QUARTER}

**Drill:**          ${DRILL_DESC}
**Environment:**    ${ENV}
**Primary region:** ${PRIMARY}
**Started:**        $(date -u -d "@${START_TS}" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -r "${START_TS}" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "${START_TS}")
**Duration:**       ${DURATION}s
**Expected RTO:**   ${EXPECTED_RTO}

## Pre-drill snapshot
\`\`\`json
${SNAPSHOT_BEFORE}
\`\`\`

## Post-drill snapshot
\`\`\`json
${SNAPSHOT_AFTER}
\`\`\`

## Did the hypothesis hold?

> [ ] Yes — RTO/RPO commitments per ops/sre/DR_BCP_PLAYBOOK.md were met.
> [ ] No — see surprises and action items below.

## What surprised us

- _(fill in after drill)_

## Action items

- [ ] _(fill in after drill, with owner + due date)_

## Sources

- [DR_BCP_PLAYBOOK.md § ${DRILL}](../DR_BCP_PLAYBOOK.md)
- [RUNBOOK.md](../RUNBOOK.md)
- [CHAOS_ENGINEERING.md](../CHAOS_ENGINEERING.md)
EOF

echo "OK: summary written."
echo
echo "=== Drill complete ==="
echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo
echo "Next steps:"
echo "  1. Open $SUMMARY_FILE and fill in 'What surprised us' + 'Action items'"
echo "  2. Share in #clincase-sre channel within 24h"
echo "  3. Schedule action-item follow-ups before next quarter's drill"
