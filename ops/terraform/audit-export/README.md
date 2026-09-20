# ClinCase — Per-Tenant Audit Log Export Terraform

**Status: apply-ready stub.**

Sets up a cross-account Kinesis subscription so that **the customer's
own SIEM** receives a real-time stream of THEIR own audit log entries —
without ever seeing another customer's data.

## Why this exists

Round-9's audit log lives in `agent_runs` + `decisions` + `llm_invocations`
+ `event_outbox` tables, queryable through the Evidence Pack endpoint.
That's correct for *us*. It's not enough for a Tier-1 payer customer:

> "ClinCase's audit log doesn't help our SOC. Our security analysts
> don't have access to your DB. We need a real-time feed into our
> Splunk / Sentinel / Chronicle."

Every Tier-1 payer security team asks this. Our answer is: **CloudWatch
Logs + Kinesis cross-account subscription, partitioned per-tenant.**

## Architecture

```
ClinCase pods                                      Customer's AWS account
─────────────                                     ─────────────────────
  CloudWatch Logs (per-tenant log group)
       │
       │ Subscription Filter (FilterPattern: tenant_id=X)
       ▼
  Kinesis Data Stream (this account)
       │
       │ Cross-account read role
       ▼
  Kinesis Data Stream (customer account)         ──► Splunk Connect for Kinesis
                                                  ──► AWS Sentinel
                                                  ──► Chronicle SIEM
```

## What this provisions (per customer)

| Resource | Purpose |
|---|---|
| `aws_cloudwatch_log_group.tenant_audit` | Dedicated log group for the tenant |
| `aws_cloudwatch_log_subscription_filter.tenant_to_kinesis` | Stream this tenant's logs to Kinesis |
| `aws_kinesis_stream.tenant_audit_export` | Per-tenant Kinesis stream |
| `aws_iam_role.tenant_kinesis_consumer` | Cross-account role the customer assumes |
| `aws_iam_role_policy.tenant_kinesis_read` | Read-only on the per-tenant stream |
| `data.aws_iam_policy_document.cross_account_assume` | Trust policy with `sts:ExternalId` |

## Apply (one tenant)

```bash
cd ops/terraform/audit-export
terraform init -backend-config=backend.tfvars
terraform apply \
  -var="tenant_id=org_humana" \
  -var="customer_account_id=123456789012" \
  -var="customer_external_id=$(openssl rand -hex 16)"
```

Apply per tenant; future iteration uses `for_each` over a tenant map.

## Tenant onboarding flow

1. Customer hands us their AWS account ID.
2. We generate a fresh `external_id` (random; mitigates the [confused
   deputy](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html)).
3. We apply this Terraform with their account ID + external_id.
4. Customer's IAM team creates a role in THEIR account with:
   ```
   sts:AssumeRole on arn:aws:iam::CLINCASE:role/ClinCaseAuditExport-{tenant_id}
   sts:ExternalId == <our generated external_id>
   ```
5. Customer subscribes their Splunk / Sentinel / Chronicle to their Kinesis
   stream (Kinesis Data Stream → AWS Lambda → SIEM API).

## Cost (per tenant per month)

| Item | Approx |
|---|--:|
| CloudWatch Logs ingest (1 GB/month/tenant) | $0.50 |
| Kinesis Data Stream (1 shard, 24h retention) | $11 |
| Cross-account data transfer | $0–$5 |
| **Total** | **~$15–$20/tenant/month** |

We charge enterprise customers $200/month/tenant for this feature
(Gold-tier add-on). 10× margin → fund the SRE work to keep it healthy.

## Compliance

- **HIPAA:** the audit log is itself ePHI (per [§ 164.312(b)
  Audit Controls](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)).
  Customer's SIEM is a Business Associate. BAA must be amended.
- **CMS-0057-F § IV.D:** decision audit data must be retainable for 7 years.
  Customer can satisfy this via their SIEM's hot/cold tier.
- **HHS attestation:** real-time streaming is preferred over scheduled exports
  to satisfy "without unreasonable delay" notification language.

## Files

- `main.tf` — providers + backend
- `variables.tf` — tenant_id, customer_account_id, customer_external_id, retention_days
- `kinesis.tf` — Kinesis stream + subscription filter
- `iam.tf` — cross-account role + read policy
- `outputs.tf` — kinesis_stream_arn, role_arn, external_id

## Sources

- AWS — *Real-time processing of log data with subscriptions* — https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Subscriptions.html
- AWS — *Cross-account access to a Kinesis stream* — https://docs.aws.amazon.com/firehose/latest/dev/controlling-access.html
- Splunk Connect for Kinesis — https://splunkbase.splunk.com/app/3719/
