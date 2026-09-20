# ─── S3 cross-region replication for audit + appeals ───────────────────────
# `agent_runs` JSONB exports + appeal PDF letters live in S3 (not RDS) so
# they're cheap to retain at 7-year HIPAA scale. CRR mirrors them to the
# secondary region with RPO < 15 minutes.
#
# WHY S3 not Aurora-replicated audit: at 100K cases/day the agent_runs
# write throughput would saturate the writer. We async-batch into S3 via
# an Athena-queryable Parquet layout. See SCALING.md § "100,000 cases/day".

# --- Primary bucket ---------------------------------------------------------

resource "aws_s3_bucket" "primary_audit" {
  provider = aws.primary
  bucket   = var.primary_audit_bucket
}

resource "aws_s3_bucket_versioning" "primary_audit" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_audit.id
  versioning_configuration {
    status = "Enabled" # Required by AWS for CRR
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "primary_audit" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_audit.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.primary.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "primary_audit" {
  provider                = aws.primary
  bucket                  = aws_s3_bucket.primary_audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "primary_audit" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_audit.id
  rule {
    id     = "audit-tier-down"
    status = "Enabled"
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 180
      storage_class = "GLACIER"
    }
    expiration {
      days = 365 * 7 # 7-year HIPAA retention floor
    }
  }
}

# --- Secondary bucket -------------------------------------------------------

resource "aws_s3_bucket" "secondary_audit" {
  provider = aws.secondary
  bucket   = var.secondary_audit_bucket
}

resource "aws_s3_bucket_versioning" "secondary_audit" {
  provider = aws.secondary
  bucket   = aws_s3_bucket.secondary_audit.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "secondary_audit" {
  provider = aws.secondary
  bucket   = aws_s3_bucket.secondary_audit.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_replica_key.secondary.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "secondary_audit" {
  provider                = aws.secondary
  bucket                  = aws_s3_bucket.secondary_audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- IAM role for CRR -------------------------------------------------------

resource "aws_iam_role" "replication" {
  provider = aws.primary
  name     = "clincase-s3-crr-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "replication" {
  provider = aws.primary
  role     = aws_iam_role.replication.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket",
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging",
        ]
        Resource = [
          aws_s3_bucket.primary_audit.arn,
          "${aws_s3_bucket.primary_audit.arn}/*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags",
        ]
        Resource = "${aws_s3_bucket.secondary_audit.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
        ]
        Resource = [
          aws_kms_key.primary.arn,
          aws_kms_replica_key.secondary.arn,
        ]
      },
    ]
  })
}

# --- Replication rule -------------------------------------------------------

resource "aws_s3_bucket_replication_configuration" "primary_to_secondary" {
  provider = aws.primary
  role     = aws_iam_role.replication.arn
  bucket   = aws_s3_bucket.primary_audit.id

  rule {
    id     = "replicate-all"
    status = "Enabled"

    filter {} # Replicate everything

    delete_marker_replication { status = "Enabled" }

    destination {
      bucket        = aws_s3_bucket.secondary_audit.arn
      storage_class = "STANDARD_IA"
      encryption_configuration {
        replica_kms_key_id = aws_kms_replica_key.secondary.arn
      }
      replication_time {
        status = "Enabled"
        time   { minutes = 15 }
      }
      metrics {
        status = "Enabled"
        event_threshold { minutes = 15 }
      }
    }

    source_selection_criteria {
      sse_kms_encrypted_objects { status = "Enabled" }
    }
  }

  depends_on = [
    aws_s3_bucket_versioning.primary_audit,
    aws_s3_bucket_versioning.secondary_audit,
  ]
}
