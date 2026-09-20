# Per-tenant CloudWatch log group + Kinesis stream + subscription filter.
# Resources are named with the tenant_id so the customer's own SIEM operator
# can verify "this stream is mine" by inspecting the ARN.

resource "aws_cloudwatch_log_group" "tenant_audit" {
  name              = "/clincase/audit/${var.tenant_id}"
  retention_in_days = var.retention_days
  kms_key_id        = aws_kms_key.tenant_audit.arn
}

resource "aws_kms_key" "tenant_audit" {
  description             = "Per-tenant KMS CMK for audit log group ${var.tenant_id}"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnableRoot"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowCloudWatchLogs"
        Effect    = "Allow"
        Principal = { Service = "logs.${var.aws_region}.amazonaws.com" }
        Action = [
          "kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*",
          "kms:GenerateDataKey*", "kms:Describe*"
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_kinesis_stream" "tenant_audit_export" {
  name             = "clincase-audit-${var.tenant_id}"
  shard_count      = var.kinesis_shard_count
  retention_period = 24

  encryption_type = "KMS"
  kms_key_id      = aws_kms_key.tenant_audit.arn

  stream_mode_details {
    stream_mode = "PROVISIONED"
  }
}

# Subscription filter forwards CloudWatch log events that match this tenant
# into Kinesis. The filter pattern is what guarantees per-tenant isolation:
# only logs tagged with this tenant_id make it into this stream.
resource "aws_cloudwatch_log_subscription_filter" "tenant_to_kinesis" {
  name            = "clincase-${var.tenant_id}-to-kinesis"
  log_group_name  = aws_cloudwatch_log_group.tenant_audit.name
  filter_pattern  = "{ $.tenant_id = \"${var.tenant_id}\" }"
  destination_arn = aws_kinesis_stream.tenant_audit_export.arn
  role_arn        = aws_iam_role.cwl_to_kinesis.arn
}
