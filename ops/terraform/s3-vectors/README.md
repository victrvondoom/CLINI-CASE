# ClinCase — S3 Vectors Terraform module

**Status: apply-ready stub** — `terraform plan` produces a clean diff once
the AWS account team flips the S3 Vectors entitlement.

This module realizes ClinCase's Context Retrieval Service (Layer 3 of the
target architecture) on top of **S3 Vectors** — the AWS-native vector store
that went GA in 2026 ([AWS What's New](https://aws.amazon.com/about-aws/whats-new/)).

## Why S3 Vectors

S3 Vectors is the GA AWS-native vector index. Three properties make it the
right substrate for ClinCase's policy corpus at scale:

1. **No separate index infrastructure** — vectors live in S3 alongside the
   source documents. One IAM policy, one bucket boundary, one KMS key.
2. **Bedrock KB integration** — Bedrock Knowledge Base can use S3 Vectors
   as its underlying vector store. Bedrock retrieval calls flow through
   our existing `policy_retriever` orchestrator with zero code change.
3. **Lifecycle + retention controls** — same S3 lifecycle rules already
   required by CMS-0057-F § IV.D (7-year audit retention) apply to the
   embeddings, not just the source documents.

For ClinCase this means: the **same S3 bucket** that holds payer policy
PDFs (and is replicated cross-region per `ops/terraform/multi-region/s3.tf`)
becomes the vector index too. No new AWS service, no new procurement.

## What this module provisions

1. **`aws_s3_vectors_index`** — one index per ClinCase tenant (`clincase-policies-{org_id}`).
2. **Embedding model binding** — Amazon Titan Text Embeddings V2 by default
   (1024 dimensions, fast + cheap; production-ready).
3. **`aws_iam_role`** — least-privilege role for Bedrock KB to call
   `s3vectors:QueryIndex` on this index only.
4. **`aws_s3_bucket_policy`** patch — S3 Vectors metadata access scoped to
   the same IAM principal as the source bucket (defense in depth with the
   per-tenant KMS key from `ops/terraform/multi-region/rds.tf`).
5. **CloudWatch Logs metric filter** — `s3vectors:QueryIndex` calls per
   org, per day. Wired into the SLO `decision-tat` burn-rate alert.

## How it connects to the running app

```
                   ┌──────────────────────┐
                   │  Customer's policy   │   ← M365/SharePoint/Confluence
                   │  PDFs in S3 bucket   │     (sync from Q Business when USE_AMAZON_Q=true)
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │   S3 Vectors index   │   ← THIS MODULE
                   │   (Titan embeddings) │
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │  Bedrock KB queries  │   ← retrieval substrate
                   │  this index          │
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │  policy_retriever    │   ← ClinCase orchestrator
                   │  orchestrator        │     (app/agents/policy_retriever/orchestrator.py)
                   │   - keyword_filter   │
                   │   - q_business...    │
                   │   - llm_reranker     │
                   │   - citation_resolver│
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │  Necessity Reasoner  │
                   │  reasons over the    │
                   │  retrieved excerpts  │
                   └──────────────────────┘
```

The ClinCase code path stays unchanged. S3 Vectors is the **substrate** Bedrock
KB uses; the orchestrator just calls Bedrock retrieve. **Zero code change** in
the app — this is infra-only.

## Apply order

```bash
cd ops/terraform/s3-vectors

terraform init \
  -backend-config="bucket=clincase-tfstate-aps1" \
  -backend-config="key=s3-vectors/terraform.tfstate" \
  -backend-config="region=ap-south-1"

# Verify entitlement first
aws bedrock list-foundation-models --by-provider amazon \
  --query 'modelSummaries[?contains(modelId, `titan-embed`)].modelId'

terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars
```

## Cost

| Item | Monthly | Notes |
|---|--:|---|
| S3 Vectors storage | ~$5 | per 1M vectors at 1024 dim (Titan V2) |
| `s3vectors:QueryIndex` calls | ~$10 | at 10K cases/day × 5 retrievals/case = 50K/day |
| Bedrock Titan Embeddings ingestion | ~$3 | per million tokens embedded |
| **Total incremental** | **~$18/month** | per pilot customer |

That's 1–2 orders of magnitude cheaper than running a separate OpenSearch
Serverless cluster for the same purpose, which is why this module exists.

## Files

| File | Purpose |
|---|---|
| `main.tf`         | Terraform/providers/backend |
| `variables.tf`    | Inputs: source_bucket_arn, organization_id, embedding_model_arn |
| `s3-vectors.tf`   | The `aws_s3_vectors_index` resource + bucket-policy patch |
| `iam.tf`          | Bedrock KB role with scoped query permissions |
| `outputs.tf`      | index_arn, role_arn (for Bedrock KB Terraform / CLI to consume) |
