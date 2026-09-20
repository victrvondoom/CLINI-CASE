# ClinCase — Synthetic monitoring (multi-region /healthz canary)

**Status: apply-ready stub.**

External-probe canaries that hit `/api/v1/healthz/deep` from FOUR
geographically distributed AWS regions every minute. Black-box monitoring
sees outages BEFORE customers report them.

## Why we need this

Round-9 monitoring is internal: AWS health checks against the ALB target
group, Prometheus scrapes from the same VPC. Both are blind to:

- DNS / Route 53 issues
- ALB → pod connectivity issues across AZs
- Customer-side TLS issues
- Per-region BGP routing fluctuations
- WAF false-positive blocks

The first signal we should EVER receive about an outage is a synthetic probe
in a third-party region failing — not a customer support ticket.

## What this provisions

Per region listed in `var.probe_regions`:

| Resource | Purpose |
|---|---|
| `aws_synthetics_canary.healthz` | Runs every 60s, hits `/api/v1/healthz/deep`, asserts 200 |
| `aws_synthetics_canary.api_v2_healthz` | Same for v2 endpoint |
| `aws_cloudwatch_metric_alarm.canary_failure` | Pages on 2/3 failures within 3 min |
| `aws_iam_role.canary_runtime` | Execution role |
| `aws_s3_bucket.canary_artifacts` | Per-canary artifacts (screenshots / HARs) |

## Default probe regions

```hcl
default = ["us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"]
```

These give us coverage across NA / EU / APAC without paying for redundant
signals from same-continent regions.

## Apply

```bash
cd ops/terraform/synthetic-monitoring
terraform init -backend-config=backend.tfvars
terraform apply -var="api_endpoint=https://api.clincase.example.com" -var-file=prod.tfvars
```

## Cost

| Item | Monthly |
|---|--:|
| 4 canaries × 60s frequency × 30d | ~$33 |
| S3 artifact storage | ~$2 |
| CloudWatch alarms + SNS notifications | ~$2 |
| **Total** | **~$37/month** |

## Files

- `main.tf` — providers + backend
- `variables.tf` — endpoint + probe_regions list
- `canaries.tf` — Synthetics canaries + alarms
- `iam.tf` — execution role
- `s3.tf` — artifact bucket
- `outputs.tf`

## Sources

- AWS Synthetics — https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Synthetics_Canaries.html
- Synthetic monitoring patterns — https://aws.amazon.com/blogs/mt/use-cloudwatch-synthetics-canaries-to-detect-pre-existing-application-issues/
