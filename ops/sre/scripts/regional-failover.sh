#!/usr/bin/env bash
# ClinCase — regional failover script
#
# Promotes the secondary Aurora cluster to primary and flips Route 53 LBR
# weights to favor the new region. Used during DR-01 (full regional outage)
# per ops/sre/DR_BCP_PLAYBOOK.md.
#
# Usage:
#     ops/sre/scripts/regional-failover.sh <target-region>
#
#     ops/sre/scripts/regional-failover.sh us-east-1
#
# Pre-flight: requires AWS CLI configured + jq installed.
# Pre-flight: requires multi-region Terraform module already applied.
set -euo pipefail

TARGET_REGION="${1:-}"
GLOBAL_CLUSTER_ID="${GLOBAL_CLUSTER_ID:-clincase}"
ROUTE53_HOSTED_ZONE_ID="${ROUTE53_HOSTED_ZONE_ID:-}"
SERVICE_DNS_NAME="${SERVICE_DNS_NAME:-api.clincase.example.com}"

if [ -z "$TARGET_REGION" ]; then
    echo "USAGE: $0 <target-region>" >&2
    echo "Example: $0 us-east-1" >&2
    exit 1
fi

if [ -z "$ROUTE53_HOSTED_ZONE_ID" ]; then
    echo "ERROR: ROUTE53_HOSTED_ZONE_ID env not set" >&2
    exit 1
fi

echo "=== ClinCase Regional Failover ==="
echo "Target region: $TARGET_REGION"
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

# 1. Verify the target region's secondary cluster is healthy
echo "[1/5] Verifying secondary cluster health in $TARGET_REGION..."
SECONDARY_STATUS=$(aws rds describe-db-clusters \
    --region "$TARGET_REGION" \
    --db-cluster-identifier "${GLOBAL_CLUSTER_ID}-secondary" \
    --query 'DBClusters[0].Status' --output text 2>/dev/null || echo "MISSING")

if [ "$SECONDARY_STATUS" != "available" ]; then
    echo "ERROR: Secondary cluster status is '$SECONDARY_STATUS' (expected 'available')" >&2
    echo "ABORTING — promotion would fail. Check ops/terraform/multi-region/ apply state." >&2
    exit 2
fi
echo "OK: secondary cluster is available"

# 2. Promote the secondary to primary
echo "[2/5] Promoting secondary to primary..."
aws rds failover-global-cluster \
    --global-cluster-identifier "$GLOBAL_CLUSTER_ID" \
    --target-db-cluster-identifier "${GLOBAL_CLUSTER_ID}-secondary" \
    --region "$TARGET_REGION"
echo "OK: failover initiated (typically completes in 60-90s)"

# 3. Wait for promotion completion
echo "[3/5] Waiting for promotion to complete (max 5 min)..."
for i in {1..30}; do
    PROMOTED=$(aws rds describe-global-clusters \
        --global-cluster-identifier "$GLOBAL_CLUSTER_ID" \
        --query "GlobalClusters[0].GlobalClusterMembers[?DBClusterArn=='arn:aws:rds:${TARGET_REGION}:${AWS_ACCOUNT_ID:-UNKNOWN}:cluster:${GLOBAL_CLUSTER_ID}-secondary'].IsWriter" \
        --output text 2>/dev/null || echo "")
    if [ "$PROMOTED" == "True" ]; then
        echo "OK: promotion complete after $((i * 10))s"
        break
    fi
    echo "  ...still promoting (waited ${i}0s)"
    sleep 10
    if [ "$i" == "30" ]; then
        echo "ERROR: promotion did not complete within 5 minutes" >&2
        exit 3
    fi
done

# 4. Flip Route 53 LBR weights
echo "[4/5] Updating Route 53 LBR weights..."
CHANGE_BATCH=$(cat <<EOF
{
  "Comment": "Regional failover to ${TARGET_REGION} at $(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "${SERVICE_DNS_NAME}.",
        "Type": "A",
        "SetIdentifier": "clincase-${TARGET_REGION}",
        "Region": "${TARGET_REGION}",
        "AliasTarget": {
          "HostedZoneId": "Z00000000ABCDEFGH",
          "DNSName": "k8s-clincase-${TARGET_REGION}.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }
  ]
}
EOF
)
aws route53 change-resource-record-sets \
    --hosted-zone-id "$ROUTE53_HOSTED_ZONE_ID" \
    --change-batch "$CHANGE_BATCH"
echo "OK: Route 53 update applied (DNS propagation typically 30-60s)"

# 5. Smoke-test the new primary
echo "[5/5] Smoke-testing the new primary..."
sleep 30  # Wait for DNS propagation
HEALTH=$(curl -sf "https://${SERVICE_DNS_NAME}/api/v1/healthz" || echo "FAIL")
if [ "$HEALTH" == "FAIL" ]; then
    echo "WARNING: smoke test failed; check via ops/sre/RUNBOOK.md INC-002"
    exit 4
fi
echo "OK: $SERVICE_DNS_NAME is responsive from $TARGET_REGION"

echo
echo "=== FAILOVER COMPLETE ==="
echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo
echo "Next steps:"
echo "  1. Verify customer impact via /api/v1/healthz/deep"
echo "  2. Update on-call channel with status"
echo "  3. Schedule post-mortem within 24h per ops/sre/RUNBOOK.md"
echo "  4. After region recovery, plan reverse failover via this same script"
