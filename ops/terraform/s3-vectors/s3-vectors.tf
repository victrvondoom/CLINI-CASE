# =============================================================================
# S3 Vectors index — ClinCase policy-corpus retrieval substrate
# =============================================================================
#
# One index per ClinCase tenant. Indexed at the same encryption boundary as
# the source bucket (multi-region KMS key from ops/terraform/multi-region/
# rds.tf). Bedrock KB queries this index via the IAM role in iam.tf.

resource "aws_s3_vectors_index" "policies" {
  name              = "clincase-policies-${var.organization_id}"
  source_bucket_arn = var.source_bucket_arn
  vector_dimensions = var.vector_dimensions
  embedding_model   = var.embedding_model_arn

  # Encryption — reuse the per-tenant KMS key already provisioned by
  # ops/terraform/multi-region/rds.tf (multi-region replica). One key,
  # one tenant boundary, every layer of the data path.
  kms_key_arn = var.kms_key_arn

  # Lifecycle — match the source bucket's retention, which is set by
  # ops/terraform/multi-region/s3.tf (7-year audit minimum for CMS-0057-F § IV.D).
  # Embeddings stay queryable for the full retention window.

  tags = {
    Tier        = "context-retrieval"
    Compliance  = "CMS-0057-F-IV-D"
    TenantId    = var.organization_id
  }
}

# Patch the source bucket policy to allow Bedrock KB (via the IAM role in iam.tf)
# to read source documents during embedding refresh. The S3 Vectors index itself
# is access-controlled via aws_s3_vectors_index_access_policy below.
resource "aws_s3_vectors_index_access_policy" "policies" {
  index_arn = aws_s3_vectors_index.policies.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowBedrockKBQueryThisIndexOnly"
        Effect    = "Allow"
        Principal = { AWS = var.bedrock_kb_principal_arn }
        Action    = [
          "s3vectors:QueryIndex",
          "s3vectors:DescribeIndex",
        ]
        Resource = aws_s3_vectors_index.policies.arn
      },
      {
        Sid       = "DenyOtherActions"
        Effect    = "Deny"
        Principal = "*"
        NotAction = [
          "s3vectors:QueryIndex",
          "s3vectors:DescribeIndex",
        ]
        Resource = aws_s3_vectors_index.policies.arn
      },
    ]
  })
}

# CloudWatch log metric filter — emits the per-tenant query rate metric
# wired into the SLO definition `decision-tat` in ops/sre/SLO.yaml.
resource "aws_cloudwatch_log_metric_filter" "query_rate" {
  name           = "clincase-s3vectors-queries-${var.organization_id}"
  log_group_name = "/aws/s3vectors/clincase"
  pattern        = "{ $.eventName = \"QueryIndex\" && $.requestParameters.indexName = \"clincase-policies-${var.organization_id}\" }"

  metric_transformation {
    name      = "S3VectorsQueriesPerOrg"
    namespace = "ClinCase/Retrieval"
    value     = "1"
    dimensions = {
      OrganizationId = "$.requestParameters.requesterPrincipal"
    }
  }
}
