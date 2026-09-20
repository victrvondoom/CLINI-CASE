# ClinCase — Disaster Recovery & Business Continuity Playbook

**Audience:** ClinCase SRE rotation · Cognizant TriZetto on-call SA · auditor verifying RPO/RTO commitments

This playbook covers what we do when **a region goes away**. Companion to:
- [`RUNBOOK.md`](./RUNBOOK.md) — incident response (single-region issues)
- [`CHAOS_ENGINEERING.md`](./CHAOS_ENGINEERING.md) — preventive chaos
- [`ops/terraform/multi-region/`](../terraform/multi-region/) — apply-ready cross-region module

## RPO / RTO commitments by tenant tier

| Tier | RPO | RTO | Cost |
|---|---|---|---|
| **Bronze** | 5 min | 30 min | included in base subscription |
| **Silver** | 1 min | 5 min | +$200/month/tenant |
| **Gold** | 1 sec | 60 sec | +$1,500/month/tenant |

These map to:
- **Bronze:** RDS automated backups + Bedrock on-demand + manual failover
- **Silver:** RDS warm read-replica in secondary region + multi-AZ + manual failover
- **Gold:** Aurora Global Database (RPO 1s + auto-failover) + Bedrock Provisioned Throughput in 2 regions + Route 53 LBR with health checks

## Quarterly DR drill — 5 named scenarios

Each scenario has: **trigger**, **the call** (what we do), **success criteria**, **acceptable outcome**, **post-mortem**.

### DR-01 — `ap-south-1` regional outage (full)

**Trigger:** AWS Health declares `ap-south-1` Bedrock + RDS + EC2 simultaneously degraded. Customer impact begins.

**The call:**
1. Page primary on-call + business owner + Cognizant TriZetto on-call SA.
2. Verify multi-region module is applied (`terraform output -state=multi-region.tfstate`).
3. Promote the `us-east-1` Aurora secondary to primary:
   ```bash
   aws rds failover-global-cluster \
     --global-cluster-identifier clincase \
     --target-db-cluster-identifier clincase-secondary \
     --region us-east-1
   ```
4. Update Route 53 LBR weights to favor `us-east-1`:
   ```bash
   ./ops/sre/scripts/regional-failover.sh us-east-1
   ```
5. Update Bedrock model_id env to the `us-east-1` inference profile (e.g. `us.anthropic.claude-sonnet-4-6`).
6. Helm-upgrade workers in `us-east-1` cluster (already running but cold-cached).
7. Verify `/api/v1/healthz/deep` from a `us-east-1` synthetic probe.

**Success criteria:** RTO 60 seconds for Gold-tier · 5 min for Silver · 30 min for Bronze.

**Acceptable outcome:** Cases in flight at the moment of cutover are reaped by the janitor and requeued in `us-east-1`; processed within 10 minutes of cutover. Decision rows from the last 1 second (Gold-tier RPO) may be lost — those cases are reprocessed without coordinator action.

**Post-mortem within 24h:** Standard format from `RUNBOOK.md` § "Post-mortem template" + cross-region cost overage report.

### DR-02 — Bedrock-only `ap-south-1` outage (Aurora healthy)

**Trigger:** Bedrock 5xx storm in `ap-south-1` only; Aurora + EC2 healthy.

**The call:**
1. Verify circuit breakers in `/api/v1/llm-gateway/circuit-breakers` are OPEN for the failing model.
2. If OPEN does NOT auto-recover within 15 min, manually flip Bedrock model_id env to `us-east-1` model. Workers continue running in `ap-south-1` but call Bedrock in `us-east-1` (cross-region Bedrock latency is acceptable for this disaster).
3. Cost note: cross-region Bedrock data transfer is charged; tag the spend in CloudWatch.

**Success criteria:** Within 15 minutes, no customer-facing 5xx. Cost overage tracked separately.

### DR-03 — RDS Aurora primary write lock (data corruption suspected)

**Trigger:** A schema migration or data corruption requires an emergency rollback.

**The call:**
1. Stop write traffic immediately:
   ```bash
   kubectl scale deploy/clincase-api -n clincase --replicas=0
   kubectl scale deploy/clincase-worker -n clincase --replicas=0
   ```
2. Identify the bad transaction window via `pg_stat_activity` + audit logs.
3. Restore from the most recent automated backup that pre-dates the corruption:
   ```bash
   aws rds restore-db-cluster-to-point-in-time \
     --source-db-cluster-identifier clincase-primary \
     --db-cluster-identifier clincase-primary-restored \
     --restore-to-time 2026-05-07T10:14:00Z
   ```
4. Cut traffic over via DNS (CNAME flip, not Route 53 LBR — this is a manual cut).
5. Compare the restored DB against the CDC stream in S3 (`ops/terraform/cdc-stream/`) to identify any records lost.
6. Reprocess affected cases.

**Success criteria:** Data integrity restored within 4 hours. Customer notified per CMS-0057-F § IV.D and per BAA contractually.

### DR-04 — Cognizant TriZetto Gateway prolonged outage

**Trigger:** TriZetto AI Gateway returns 5xx for > 30 minutes; affects all our customer's downstream Facets workflow.

**The call:**
1. ClinCase case decisions still write to our DB. **No data loss.**
2. The TriZetto submit step in the saga goes into the "pending compensation" state ([`SAGA_PATTERN.md`](../architecture/SAGA_PATTERN.md)).
3. Coordinator UI shows: "Decision recorded. TriZetto Gateway temporarily unavailable; submit will be retried in the background."
4. Background retry worker drains the pending submits when Gateway recovers.
5. Notify Cognizant TriZetto on-call SA per [`RUNBOOK.md`](./RUNBOOK.md) escalation table.

**Success criteria:** Zero in-house data loss. Submits drain within 60 minutes of Gateway recovery.

### DR-05 — Total ClinCase multi-tenant compromise (security incident)

**Trigger:** A vulnerability disclosure indicates that a single-tenant compromise may have lateral movement across tenants.

**The call:**
1. **Stop all production traffic immediately:**
   ```bash
   kubectl scale deploy/clincase-api -n clincase --replicas=0
   kubectl scale deploy/clincase-worker -n clincase --replicas=0
   ```
2. Page primary + business owner + Cognizant Health Sciences vertical lead.
3. Rotate every secret in AWS Secrets Manager.
4. Rotate the per-tenant Bedrock Guardrail IDs (regenerate via Terraform).
5. Force every JWT to be revoked (issue a JWT_SECRET rotation; users re-login).
6. Spin up a parallel "clean" cluster in a fresh AWS account; restore data from CDC stream snapshots.
7. Compose customer notification per BAA contractually.

**Success criteria:** Production restored to a known-clean state within 24 hours. Customer notification within 72 hours per HIPAA Breach Notification Rule.

## Quarterly drill calendar

| Q | Drill | Owner |
|---|---|---|
| Q1 | DR-01 (full regional outage) | TL + Cognizant TriZetto SA |
| Q2 | DR-02 (Bedrock-only outage) | TL |
| Q3 | DR-03 (data corruption) | TL + DBA |
| Q4 | DR-04 (TriZetto Gateway outage) | TL + Cognizant TriZetto SA |
| Annual | DR-05 (security tabletop) | TL + business owner + safety contact |

Each drill ends with a 1-page write-up at `ops/sre/dr-results/DR-NN-YYYY-Q.md` covering: did we hit RTO? what surprised us? what action items?

## What's NOT covered (and why)

- **Bedrock data sovereignty incident** — out of scope for ClinCase; AWS regulates this. Our action is "comply with AWS guidance."
- **Earthquake / data center physical destruction** — covered by AWS multi-AZ inside one region + multi-region between regions. Our action is "this is what multi-region buys you."
- **Anthropic model removal / deprecation** — covered by `ModelRouter` + the `tenant_policies.allowed_model_ids` allowlist mechanism (ADR-0006).

## Who declares "disaster"

- **Bronze tier:** primary on-call.
- **Silver tier:** primary on-call + business owner approval.
- **Gold tier:** business owner approval required (Gold customers have contractual notification windows).

## Sources

- AWS Disaster Recovery Best Practices — https://aws.amazon.com/disaster-recovery/
- HIPAA Breach Notification Rule — https://www.hhs.gov/hipaa/for-professionals/breach-notification/
- RPO/RTO definitions — Google SRE workbook
