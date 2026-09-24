# =============================================================================
# Kinesis Data Stream + Firehose → S3 Parquet audit lake
# =============================================================================

resource "aws_kinesis_stream" "clincase_cdc" {
  name             = "clincase-cdc"
  shard_count      = 1   # bump per Gold-tier pilot when sustained > 10 MB/s
  retention_period = 168  # hours = 7 days
  encryption_type  = "KMS"
  kms_key_id       = var.kms_key_arn
  stream_mode_details { stream_mode = "PROVISIONED" }
}

resource "aws_s3_bucket" "cdc_lake" {
  bucket = "clincase-cdc-lake-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "cdc_lake" {
  bucket = aws_s3_bucket.cdc_lake.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cdc_lake" {
  bucket = aws_s3_bucket.cdc_lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "cdc_lake" {
  bucket                  = aws_s3_bucket.cdc_lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "cdc_lake" {
  bucket = aws_s3_bucket.cdc_lake.id
  rule {
    id     = "audit-tier-down"
    status = "Enabled"
    transition { days = 90;  storage_class = "STANDARD_IA" }
    transition { days = 180; storage_class = "GLACIER" }
    expiration { days = var.lake_retention_days }
  }
}

resource "aws_iam_role" "firehose_s3" {
  name = "clincase-firehose-s3"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "firehose.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "sts:ExternalId" = data.aws_caller_identity.current.account_id } }
    }]
  })
}

resource "aws_iam_role_policy" "firehose_s3" {
  role = aws_iam_role.firehose_s3.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:AbortMultipartUpload", "s3:GetBucketLocation", "s3:GetObject", "s3:ListBucket", "s3:ListBucketMultipartUploads", "s3:PutObject"]
        Resource = [aws_s3_bucket.cdc_lake.arn, "${aws_s3_bucket.cdc_lake.arn}/*"]
      },
      {
        Effect = "Allow"
        Action = ["kinesis:GetRecords", "kinesis:GetShardIterator", "kinesis:DescribeStream", "kinesis:ListShards"]
        Resource = aws_kinesis_stream.clincase_cdc.arn
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = var.kms_key_arn
      },
      {
        Effect = "Allow"
        Action = ["glue:GetTable", "glue:GetTableVersion", "glue:GetTableVersions"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_kinesis_firehose_delivery_stream" "cdc_to_s3" {
  name        = "clincase-cdc-to-s3"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.clincase_cdc.arn
    role_arn           = aws_iam_role.firehose_s3.arn
  }

  extended_s3_configuration {
    role_arn        = aws_iam_role.firehose_s3.arn
    bucket_arn      = aws_s3_bucket.cdc_lake.arn
    buffering_size  = 64    # MB
    buffering_interval = 60 # seconds
    compression_format = "UNCOMPRESSED"
    prefix = "table=!{partitionKeyFromQuery:table_name}/dt=!{timestamp:yyyy-MM-dd}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/!{timestamp:yyyy-MM-dd}/"

    data_format_conversion_configuration {
      enabled = true
      input_format_configuration {
        deserializer { open_x_json_ser_de {} }
      }
      output_format_configuration {
        serializer { parquet_ser_de {} }
      }
      schema_configuration {
        database_name = aws_glue_catalog_database.clincase_audit.name
        role_arn      = aws_iam_role.firehose_s3.arn
        table_name    = "cdc_events"
        region        = var.aws_region
      }
    }

    dynamic_partitioning_configuration { enabled = true }
    processing_configuration {
      enabled = true
      processors {
        type = "MetadataExtraction"
        parameters {
          parameter_name  = "MetadataExtractionQuery"
          parameter_value = "{table_name: .metadata.\"table-name\"}"
        }
        parameters {
          parameter_name  = "JsonParsingEngine"
          parameter_value = "JQ-1.6"
        }
      }
    }
  }
}
