# ClinCase — Multi-region active/active Terraform module

**Status: apply-ready** — `terraform init && terraform plan` will produce a
diff against an empty state. Procurement is the only blocker (cross-region
Aurora Global + Route53 LBR are paid AWS services).

## What this module does

Stands up a second-region replica of the entire ClinCase stack so a regional
AWS outage doesn't take ClinCase down. The math: Bedrock-on-AWS uptime is
99.9% per region. Two regions in active/active gets us 99.9999% effective
availability — a 1,000× reduction in expected downtime.

Specifically:

1. **Aurora Global Database** — primary cluster in `ap-south-1`, secondary
   in `us-east-1`. Cross-region replication latency < 1s typical. Promote
   to primary during a regional failover; ~60-90s RTO, ~1s RPO.
2. **Route 53 latency-based routing** — a single `clincase.example.com`
   record fans out to the closest healthy regional ALB. Sub-second client
   failover when a region's ALB starts failing health checks.
3. **Bedrock dual-region invocation** — workers in each region invoke their
   local Bedrock; no cross-region Bedrock traffic (cost + latency).
4. **S3 cross-region replication** — `agent_runs` JSONB exports + appeal
   PDFs replicated via S3 CRR. RPO < 15 min.
5. **Multi-region IAM** — IRSA roles in each region's EKS cluster bound to
   the same KMS key for envelope encryption (key replicated cross-region).

## What this module does NOT do

- **Provision EKS clusters** — out of scope; assumes both clusters already
  exist (use the existing `eksctl create cluster` workflow per region).
- **Deploy ClinCase pods** — that's `ops/k8s/`. This module wires the
  *infrastructure* across regions; pods are deployed by ArgoCD per region
  with the same manifests.
- **Switch the application's Bedrock region runtime** — the worker reads
  `AWS_REGION` from its env. Each region's K8s deployment sets it to the
  local region.

## Prerequisites

Before running `terraform apply`:

1. Two AWS accounts (or sub-accounts) — `clincase-prod-aps1`, `clincase-prod-use1`
2. VPCs in each region peered with the existing on-prem VPN gateway (no
   public-internet egress, per HIPAA Privacy Rule)
3. An S3 bucket for Terraform state with cross-region replication enabled
   (so a region loss doesn't lose the state file itself)
4. `BEDROCK_KB_ID` for both regions — Bedrock KB is regional, so we
   maintain two parallel KBs and a cron-replication job for source docs.
   This is documented in `ops/aws/MIGRATION_RUNBOOK.md` § 4.

## Cost impact (incremental over single-region prod)

| Line item                          | Monthly $  | Notes |
|------------------------------------|-----------:|-------|
| Aurora Global secondary cluster    | $1,100     | db.r6g.xlarge × 1 (warm-standby) |
| Route 53 LBR + health checks       | $50        | 2 health checks @ $0.50 + DNS queries |
| S3 CRR transfer + storage          | $80        | 100 GB/month replication |
| Bedrock provisioned throughput × 2 | (separate) | See `../provisioned-throughput/` |
| Cross-region data transfer         | $200       | RDS replication egress |
| **Incremental total**              | **$1,430** | |

Single-region prod is $1,200/month. Multi-region active/active is $2,630/month.
This is the cost of 99.9999% vs 99.9%.

## Apply order

```bash
cd ops/terraform/multi-region

# 1. Bootstrap state backend (one-time)
terraform init \
  -backend-config="bucket=clincase-tfstate-aps1" \
  -backend-config="key=multi-region/terraform.tfstate" \
  -backend-config="region=ap-south-1"

# 2. Plan against AWS (expect ~25 resources to add)
terraform plan -var-file=prod.tfvars

# 3. Apply phased — RDS first, then Route 53, then S3
terraform apply -target=aws_rds_global_cluster.clincase -var-file=prod.tfvars
terraform apply -target=aws_rds_cluster.secondary -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars

# 4. Verify replication is healthy
aws rds describe-global-clusters --global-cluster-identifier clincase \
  --query 'GlobalClusters[0].GlobalClusterMembers[*].{Region:Region,Writer:IsWriter}'
```

## Rollback

```bash
# Promote secondary to primary (regional failover drill)
aws rds failover-global-cluster \
  --global-cluster-identifier clincase \
  --target-db-cluster-identifier clincase-secondary

# Update Route 53 to weight us-east-1 to 100%
terraform apply -var=primary_region=us-east-1 -var-file=prod.tfvars
```

## Files

| File | Purpose |
|---|---|
| `main.tf`         | Terraform/providers (aws.primary, aws.secondary) |
| `variables.tf`    | All inputs — regions, sizing, account IDs, db credentials |
| `rds.tf`          | Aurora Global Database — primary + secondary clusters |
| `route53.tf`      | Hosted zone + LBR records + health checks |
| `s3.tf`           | Cross-region replication for trace + appeal exports |
| `outputs.tf`      | Connection strings, R53 zone ID, IAM role ARNs |
