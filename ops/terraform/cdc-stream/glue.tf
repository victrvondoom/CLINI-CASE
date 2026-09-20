# =============================================================================
# Glue Catalog + Athena workgroup for the audit lake
# =============================================================================

resource "aws_glue_catalog_database" "clincase_audit" {
  name        = "clincase_audit"
  description = "ClinCase CDC audit lake — one table per Postgres source table, Parquet on S3."
}

resource "aws_iam_role" "glue_crawler" {
  name = "clincase-glue-crawler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "glue_crawler" {
  role = aws_iam_role.glue_crawler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.cdc_lake.arn, "${aws_s3_bucket.cdc_lake.arn}/*"]
      },
      {
        Effect = "Allow"
        Action = ["glue:*"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:DescribeKey"]
        Resource = var.kms_key_arn
      },
    ]
  })
}

resource "aws_glue_crawler" "clincase_audit_tables" {
  name          = "clincase-audit-crawler"
  database_name = aws_glue_catalog_database.clincase_audit.name
  role          = aws_iam_role.glue_crawler.arn
  schedule      = "cron(0 1 * * ? *)" # 01:00 UTC daily

  s3_target {
    path = "s3://${aws_s3_bucket.cdc_lake.bucket}/"
  }

  configuration = jsonencode({
    Version    = 1.0
    CrawlerOutput = { Partitions = { AddOrUpdateBehavior = "InheritFromTable" } }
  })
}

resource "aws_athena_workgroup" "clincase_audit" {
  name = "clincase-audit"
  configuration {
    enforce_workgroup_configuration   = true
    publish_cloudwatch_metrics_enabled = true
    result_configuration {
      output_location = "s3://${aws_s3_bucket.cdc_lake.bucket}/athena-results/"
      encryption_configuration {
        encryption_option = "SSE_KMS"
        kms_key_arn       = var.kms_key_arn
      }
    }
    bytes_scanned_cutoff_per_query = 10737418240 # 10 GB cap per query
  }
}
