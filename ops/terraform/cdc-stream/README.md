# ClinCase — CDC Stream Terraform module (Postgres → Kinesis → S3 audit lake)

**Status: apply-ready stub.**

Captures every change to ClinCase's domain tables (`cases`, `decisions`, `appeals`, `agent_runs`, `reviewer_actions`, `event_outbox`) via Postgres logical replication, streams to Kinesis, lands in S3 + Glue catalog as Parquet for Athena queries.

This is the **scale primitive** that takes ClinCase from "10K cases/day Aurora-only" to "millions of cases/day with cheap analytics."

## Why CDC

At 100K cases/day:
- Aurora's per-row Postgres write becomes the bottleneck for `agent_runs` (~14 inserts/sec sustained).
- Audit queries against `agent_runs` (Evidence Pack, compliance scorecard rollups) start contending with hot OLTP writes.
- Per-customer "give me all decisions in 2026 Q3" requires expensive SQL.

CDC solution:
- Aurora keeps OLTP load only.
- AWS DMS (or self-hosted Debezium) reads logical replication slot → Kinesis.
- Firehose lands Kinesis records as Parquet in S3, partitioned by `(date, organization_id, table)`.
- Glue catalog exposes the Parquet to Athena.
- Customer / compliance officer / partner analytics: one SQL query in Athena, no Aurora load.

## Architecture

```
┌──────────────┐    logical    ┌───────────┐    ┌──────────────┐    ┌─────────────────┐
│  RDS Aurora  │  replication  │  AWS DMS  │ →  │  Kinesis     │ →  │ Kinesis Firehose│
│  (ClinCase)   │  ────────────►│  task     │    │  Data Stream │    │ → S3 Parquet    │
└──────────────┘               └───────────┘    └──────────────┘    └────────┬────────┘
                                                                              │
                                                              ┌───────────────┼─────────────────┐
                                                              ▼                                 ▼
                                                       ┌───────────┐                    ┌─────────────┐
                                                       │ Glue       │                    │ S3 Lifecycle│
                                                       │ Catalog    │                    │ → Glacier   │
                                                       │ (DB+tables)│                    │ at 7 years  │
                                                       └─────┬──────┘                    └─────────────┘
                                                             │
                                                             ▼
                                                       ┌───────────┐
                                                       │ Athena    │  ← customer / SRE / compliance officer
                                                       │ queries   │
                                                       └───────────┘
```

## What this provisions

| Resource | Purpose |
|---|---|
| `aws_kinesis_stream.clincase_cdc` | The CDC firehose's source stream |
| `aws_dms_replication_instance.clincase` | DMS instance for the Aurora source |
| `aws_dms_endpoint.aurora_source` | Source endpoint pointing at Aurora |
| `aws_dms_endpoint.kinesis_target` | Target endpoint pointing at the Kinesis stream |
| `aws_dms_replication_task.clincase_to_kinesis` | The replication task (full-load + ongoing CDC) |
| `aws_kinesis_firehose_delivery_stream.cdc_to_s3` | Buffers Kinesis records into Parquet on S3 |
| `aws_s3_bucket.cdc_lake` | Audit-lake bucket with Glacier lifecycle |
| `aws_glue_catalog_database.clincase_audit` | Glue catalog for Athena |
| `aws_glue_crawler.clincase_audit_tables` | Per-table crawler that creates Athena tables |

## Apply

```bash
cd ops/terraform/cdc-stream
terraform init -backend-config=backend.tfvars
terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars

# After apply, configure Aurora's logical replication slot:
psql $DATABASE_URL -c "ALTER SYSTEM SET rds.logical_replication = 1;"
# (requires DB restart)
```

## Cost

| Item | Monthly |
|---|--:|
| DMS `dms.t3.medium` instance | $50 |
| Kinesis Data Stream (1 shard, 10 KB/s) | $11 |
| Kinesis Firehose (~5 GB/day) | $30 |
| S3 storage (~150 GB/month at 100K cases/day, 7-year retention) | $4 |
| Glue Crawler + Catalog | $5 |
| Athena queries (per-customer, per audit) | ~$2 per audit |
| **Total** | **~$100/month** at 10K cases/day · ~$700/month at 100K cases/day |

vs Aurora scale-up to handle the same OLTP+OLAP load: **~$2,000/month additional**. CDC is 3-15× cheaper.

## Files

- `main.tf` — providers + backend
- `variables.tf` — Aurora ARN, target region, retention
- `dms.tf` — DMS instance + endpoints + replication task
- `kinesis.tf` — Stream + Firehose + S3 bucket
- `glue.tf` — Catalog + crawler + Athena workgroup
- `outputs.tf` — bucket ARN, stream ARN, Athena workgroup
