# Two roles:
#   1. cwl_to_kinesis  — used by CloudWatch Logs to put records into Kinesis
#   2. tenant_consumer — assumed by the CUSTOMER's account to read the stream

# -----------------------------------------------------------------------------
# 1) CWL → Kinesis (intra-account)
# -----------------------------------------------------------------------------
resource "aws_iam_role" "cwl_to_kinesis" {
  name = "ClinCaseCWLToKinesis-${var.tenant_id}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "logs.${var.aws_region}.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "cwl_to_kinesis" {
  role = aws_iam_role.cwl_to_kinesis.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["kinesis:PutRecord", "kinesis:PutRecords"]
      Resource = aws_kinesis_stream.tenant_audit_export.arn
    }]
  })
}

# -----------------------------------------------------------------------------
# 2) Cross-account consumer role — customer assumes this from THEIR account
# -----------------------------------------------------------------------------
resource "aws_iam_role" "tenant_consumer" {
  name = "ClinCaseAuditExport-${var.tenant_id}"

  # The trust policy:
  #   - Only the customer's account principal can assume
  #   - sts:ExternalId must match (confused-deputy mitigation)
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${var.customer_account_id}:root" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "sts:ExternalId" = var.customer_external_id
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "tenant_consumer_read" {
  role = aws_iam_role.tenant_consumer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadStream"
        Effect = "Allow"
        Action = [
          "kinesis:DescribeStream",
          "kinesis:DescribeStreamSummary",
          "kinesis:GetShardIterator",
          "kinesis:GetRecords",
          "kinesis:ListShards",
          "kinesis:SubscribeToShard",
        ]
        Resource = aws_kinesis_stream.tenant_audit_export.arn
      },
      {
        Sid    = "DecryptForKinesis"
        Effect = "Allow"
        Action = ["kms:Decrypt"]
        Resource = aws_kms_key.tenant_audit.arn
      },
    ]
  })
}
