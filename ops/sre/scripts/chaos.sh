#!/usr/bin/env bash
# ClinCase — chaos experiment trigger script
#
# Wraps `aws fis start-experiment` with safety gates:
#  - Refuses to run against production unless --i-know-what-i-am-doing flag is passed
#  - Tails CloudWatch logs in real time
#  - Captures the SLO snapshot at start + finish
#
# Usage:
#     ops/sre/scripts/chaos.sh <experiment-id>
#     ops/sre/scripts/chaos.sh EXP-02
#
# Environment:
#     CLINCASE_ENV=staging|prod   (default: staging — refuses prod without --force)
set -euo pipefail

EXPERIMENT="${1:-}"
FORCE_FLAG="${2:-}"
ENV="${CLINCASE_ENV:-staging}"

if [ -z "$EXPERIMENT" ]; then
    echo "USAGE: $0 <EXP-NN> [--i-know-what-i-am-doing]" >&2
    echo "Available experiments:" >&2
    echo "  EXP-01  Bedrock 5xx storm (proxy: scale workers to 0)" >&2
    echo "  EXP-02  Worker pod kill" >&2
    echo "  EXP-03  RDS Aurora primary failover" >&2
    echo "  EXP-04  Redis ElastiCache failover" >&2
    echo "  EXP-05  TriZetto Gateway block (NACL rule)" >&2
    exit 1
fi

if [ "$ENV" == "prod" ] && [ "$FORCE_FLAG" != "--i-know-what-i-am-doing" ]; then
    echo "ERROR: Refusing to run chaos against PRODUCTION without --i-know-what-i-am-doing flag" >&2
    echo "Set CLINCASE_ENV=staging or pass the flag explicitly" >&2
    exit 2
fi

echo "=== ClinCase Chaos Experiment: $EXPERIMENT ==="
echo "Environment: $ENV"
echo "Started:     $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

# Capture pre-experiment SLO snapshot
echo "[1/4] Capturing pre-experiment SLO snapshot..."
SLO_SNAPSHOT_BEFORE=$(curl -sf http://localhost:8000/api/v1/healthz/deep 2>/dev/null | jq -r '.status' || echo "?")
echo "  Cluster status before: $SLO_SNAPSHOT_BEFORE"

# Look up FIS template ID
echo "[2/4] Looking up FIS template ID for $EXPERIMENT..."
TEMPLATE_ID=$(aws fis list-experiment-templates \
    --query "experimentTemplates[?tags.Name=='${EXPERIMENT}-pod-kill' || tags.Name=='${EXPERIMENT}-rds-failover' || tags.Name=='${EXPERIMENT}-redis-failover' || tags.Name=='${EXPERIMENT}-bedrock-throttle-proxy'].id" \
    --output text | head -1)

if [ -z "$TEMPLATE_ID" ]; then
    echo "ERROR: No FIS template found for $EXPERIMENT" >&2
    echo "  Did you apply ops/terraform/fis/?" >&2
    exit 3
fi
echo "  Template: $TEMPLATE_ID"

# Start experiment
echo "[3/4] Starting experiment..."
EXPERIMENT_ID=$(aws fis start-experiment \
    --experiment-template-id "$TEMPLATE_ID" \
    --query 'experiment.id' --output text)
echo "  Experiment ID: $EXPERIMENT_ID"
echo "  Live status:   aws fis get-experiment --id $EXPERIMENT_ID"

# Wait for completion
echo "[4/4] Waiting for experiment to complete (CTRL-C to stop)..."
while true; do
    STATUS=$(aws fis get-experiment --id "$EXPERIMENT_ID" --query 'experiment.state.status' --output text)
    echo "  $(date -u +%H:%M:%S) status=$STATUS"
    case "$STATUS" in
        completed|stopped|failed)
            break
            ;;
    esac
    sleep 15
done

# Capture post-experiment SLO snapshot
SLO_SNAPSHOT_AFTER=$(curl -sf http://localhost:8000/api/v1/healthz/deep 2>/dev/null | jq -r '.status' || echo "?")

echo
echo "=== Experiment Complete ==="
echo "Finished:    $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Final state: $STATUS"
echo "Cluster status before: $SLO_SNAPSHOT_BEFORE"
echo "Cluster status after:  $SLO_SNAPSHOT_AFTER"
echo
echo "Next steps:"
echo "  1. Compare /api/v1/llm-gateway/circuit-breakers state pre/post"
echo "  2. Pull experiment logs: aws logs filter-log-events --log-group-name /aws/fis/clincase"
echo "  3. Write 1-page summary to ops/sre/chaos-results/${EXPERIMENT}-$(date +%Y-Q$(date +%m | awk '{print int(($1+2)/3)}')).md"
