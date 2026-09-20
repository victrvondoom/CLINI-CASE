# ClinCase — Terraform modules

Apply-ready infrastructure-as-code for the production scaling levers in
`ops/SCALING.md`. Both modules are gated by AWS procurement (multi-region
needs cross-region Aurora; provisioned throughput needs the per-month
commit), but neither needs additional code or design — just credentials
and a `terraform apply`.

## Modules

| Module | Purpose | Monthly $ |
|---|---|--:|
| [`multi-region/`](./multi-region/)                 | Active/active deployment across `ap-south-1` + `us-east-1`. Aurora Global Database, Route 53 LBR, S3 CRR. | +$1,430 over single-region |
| [`provisioned-throughput/`](./provisioned-throughput/) | Bedrock provisioned throughput (1 MU Sonnet + 1 MU Haiku, 1-month commit). Locks predictable LLM capacity. | +$63,510 |

## Apply order at production

```bash
# 1. Provisioned throughput FIRST — pre-warm capacity before traffic arrives
cd ops/terraform/provisioned-throughput
terraform init -backend-config=backend.tfvars
terraform apply -var-file=prod.tfvars

# 2. Multi-region SECOND — assumes provisioned throughput exists in both regions
cd ops/terraform/multi-region
terraform init -backend-config=backend.tfvars
terraform apply -var-file=prod.tfvars
```

## State backend

Both modules expect:
  - S3 bucket `clincase-tfstate-aps1` (versioning enabled, KMS encrypted)
  - DynamoDB table `clincase-tfstate-locks` (PK = `LockID`)

Bootstrap in a one-time `terraform init`-only project before applying these.

## CI/CD integration

`make tf.plan.multi-region` and `make tf.plan.provisioned-throughput` run a
`terraform plan` from CI on every PR that touches `ops/terraform/**`. The
plan output is posted to the PR; apply stays manual (these are paid-resource
modules — no auto-apply, ever).
