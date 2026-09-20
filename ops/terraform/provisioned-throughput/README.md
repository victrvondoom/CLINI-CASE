# ClinCase — Bedrock Provisioned Throughput Terraform module

**Status: apply-ready** — `terraform init && terraform plan` produces a clean
diff. The procurement gate is the per-month commit (~$15K/month per Sonnet
model unit at the time of writing; verify in the AWS pricing API before apply).

## Why this module exists

At 10K+ cases/day, on-demand Bedrock TPM (tokens-per-minute) is the binding
constraint, not vCPU or RAM. A single `apac.anthropic.claude-sonnet-4-6`
on-demand limit in `ap-south-1` is **400K input TPM** and **80K output TPM**.

ClinCase per-case math (see `ops/SCALING.md`):
- Sonnet input: ~24,000 tokens / case
- Sonnet output: ~4,500 tokens / case
- DAG runtime: ~52 s / case (clean APPROVE)

That's a **~28K input tokens / 5K output tokens × 60 / 52 ≈ 32K input TPM
and 5.8K output TPM per concurrent case**. On-demand quota covers ~12-13
concurrent cases peak. Production tier (200 concurrent) needs **dedicated
provisioned throughput**.

## What this module provisions

1. **One model unit (MU) of Sonnet 4.6** in `ap-south-1`. 1 MU ≈ 600K input
   TPM + 100K output TPM ≈ 18-20 concurrent cases.
2. **One model unit (MU) of Haiku 4.5** in `ap-south-1`. 1 MU of Haiku is
   *much* cheaper but covers our deterministic graders / lite-extractor
   sub-agents.
3. **CloudWatch alarms** on:
   - `Bedrock.ProvisionedModelThroughput.Utilization > 80%` for 5m → P3
   - `Bedrock.ProvisionedModelThroughput.Utilization > 95%` for 2m → P2
4. **A model copy in us-east-1** (for the multi-region module's failover
   path). Optional — gated by `var.enable_secondary_region`.

## Cost

| Resource                                | Hourly | Monthly (730h) | Commitment |
|---|--:|--:|---|
| 1 MU Sonnet 4.6 (apac)                  | $90.00 | $65,700        | 1-month no-commit |
| 1 MU Sonnet 4.6 (apac)                  | $63.00 | $45,990        | 1-month commit (30% discount) |
| 1 MU Sonnet 4.6 (apac)                  | $44.10 | $32,193        | 6-month commit (51% discount) |
| 1 MU Haiku 4.5 (apac)                   | $24.00 | $17,520        | 1-month no-commit |
| **Default config (1 MU Sonnet, 1 MU Haiku, 1-month commit)** | | **$63,510** | |

Pricing source: AWS Bedrock pricing page (verify before apply, this changes).

**Why we pay this**: 1 MU of Sonnet handles ~18-20 concurrent cases at
50-second p50. Production tier is 200 concurrent → we need 10 MU. At 100K
cases/day Scale tier, we need ~30 MU. The on-demand bursts during a payer
go-live event would otherwise simply hit AWS throttling and queue depth
would explode.

## Apply order

```bash
cd ops/terraform/provisioned-throughput

terraform init \
  -backend-config="bucket=clincase-tfstate-aps1" \
  -backend-config="key=provisioned-throughput/terraform.tfstate" \
  -backend-config="region=ap-south-1"

terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars   # Takes ~10 min for Bedrock to allocate
```

Once applied, the worker tier picks up the new throughput automatically
because it just calls `bedrock.invoke_model()` with the same model_id; the
provisioned model ARN is implicit in the account's quota.

## Rollback

```bash
# Releases the provisioned throughput, reverts to on-demand billing
terraform destroy -target=aws_bedrock_provisioned_model_throughput.sonnet_primary
```

If you need to scale UP rather than down (e.g. a payer pushed cases earlier
than expected), edit `model_units` in `provisioned-throughput.tf` and
`terraform apply` — AWS allocates the additional units in ~10 min.

## Files

| File | Purpose |
|---|---|
| `main.tf`                         | Providers, version constraints, S3 backend |
| `variables.tf`                    | All inputs — model IDs, MU counts, regions, commit tier |
| `provisioned-throughput.tf`       | The actual `aws_bedrock_provisioned_model_throughput` resources |
| `cloudwatch-alarms.tf`            | Utilization alarms wired to PagerDuty SNS |
| `outputs.tf`                      | Provisioned model ARNs, alarm ARNs |
