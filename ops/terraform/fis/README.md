# ClinCase — AWS Fault Injection Simulator (FIS) Terraform module

**Status: apply-ready stub.** Closes the gap between `ops/sre/CHAOS_ENGINEERING.md` (the playbook) and *"actually run it on demand."*

This module provisions FIS templates for the 5 named chaos experiments. Operators trigger experiments via:

```bash
aws fis start-experiment --experiment-template-id <ID>
```

…or via the wrapper script `ops/sre/scripts/chaos.sh`.

## What this provisions

| FIS template | Experiment | What FIS does |
|---|---|---|
| `clincase-EXP-01-bedrock-throttle` | EXP-01 — Bedrock 5xx storm | Injects throttling on Bedrock InvokeModel for 5 min |
| `clincase-EXP-02-pod-kill` | EXP-02 — Worker pod kill | Terminates a random `clincase-worker` pod 30s after start |
| `clincase-EXP-03-rds-failover` | EXP-03 — Postgres primary failover | Forces RDS Aurora cluster failover |
| `clincase-EXP-04-redis-stop` | EXP-04 — Redis outage | Stops the Redis ElastiCache primary |
| `clincase-EXP-05-trizetto-block` | EXP-05 — TriZetto rejection | Egress NACL rule blocks `TRIZETTO_GATEWAY_URL` for 5 min |

Each template has explicit:
- **Stop conditions** (CloudWatch alarm-based; auto-stops if the experiment goes wrong)
- **IAM execution role** scoped to the specific actions
- **CloudWatch Logs target** for experiment lifecycle events

## Apply

```bash
cd ops/terraform/fis
terraform init -backend-config=backend.tfvars
terraform apply -var-file=prod.tfvars
```

After apply, run an experiment:

```bash
ops/sre/scripts/chaos.sh EXP-01    # → starts the Bedrock throttle experiment
```

## Cost

| Item | Per experiment |
|---|--:|
| FIS experiment run | $0.10 / action / minute |
| Per 5-min run with 2 actions | ~$1 |
| Quarterly drill (5 experiments × 4) = 20 runs | ~$20 / year |

## Files

- `main.tf` — providers + backend
- `variables.tf` — region, account_id, EKS cluster name, RDS cluster ID
- `iam.tf` — FIS execution role + the 5 action permissions
- `experiments.tf` — the 5 `aws_fis_experiment_template` resources
- `outputs.tf` — experiment template IDs (consumed by `ops/sre/scripts/chaos.sh`)
