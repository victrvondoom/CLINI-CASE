# ClinCase — AWS WAF Terraform module

**Status: apply-ready stub.**

Realizes the AWS-published guidance for production-grade web-application firewall in front of ClinCase's ALB:

- **AWS-managed rule sets** (OWASP Top 10 + Known-Bad-Inputs + SQLi + XSS)
- **Rate-based rules per tenant tier** (Bronze 10 r/s, Silver 50, Gold 200)
- **Geo-restriction** for the Bronze tier (single-country)
- **CloudWatch alarms** on blocked-request anomaly

## Why this exists

- Healthcare API in front of a payer is a high-value target for credential stuffing / SQLi / scraping. AWS WAF is the AWS-blessed defense.
- Per-tenant rate limits enforce the SLA tier from `org_quotas.tier` at the network edge — **before** the request hits the application's per-tenant quota check (defense in depth).
- OWASP Top 10 managed rule sets are required by every Cognizant TriZetto customer's security questionnaire.

## What this provisions

| Resource | Purpose |
|---|---|
| `aws_wafv2_web_acl.clincase` | Top-level Web ACL attached to the ALB |
| `aws_wafv2_web_acl_association.clincase_alb` | Associates the WACL to the ALB ARN passed in |
| `aws_wafv2_rule_group.tenant_tier_rate_limits` | Per-tier rate-based rules (Bronze/Silver/Gold) |
| `aws_cloudwatch_log_group.waf_logs` | Sampled-request log group (90-day retention) |
| `aws_cloudwatch_metric_alarm.blocked_request_spike` | P3 alarm on blocked-request anomaly |

## Apply

```bash
cd ops/terraform/waf
terraform init -backend-config=backend.tfvars
terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars
```

## Cost

| Item | Monthly |
|---|--:|
| WACL | $5 |
| 5 rules (4 managed + 1 rate-based) | $5 |
| Per-1M requests | $0.60 |
| WAF logging to CloudWatch | ~$3 |
| **Total** | **~$15-25/month** |

## Files

- `main.tf` — providers + backend
- `variables.tf` — `alb_arn`, region, log retention, per-tier rate limits
- `wacl.tf` — Web ACL with managed rules + rate-based rules + association
- `cloudwatch.tf` — log group + alarm
- `outputs.tf` — wacl_arn (for CloudFront / additional ALB association)
