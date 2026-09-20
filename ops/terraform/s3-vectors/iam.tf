# =============================================================================
# IAM — Bedrock KB role with least-privilege query access to this index only
# =============================================================================

data "aws_iam_policy_document" "bedrock_kb_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "bedrock_kb" {
  name               = "clincase-bedrock-kb-${var.organization_id}"
  assume_role_policy = data.aws_iam_policy_document.bedrock_kb_assume.json
  description        = "Bedrock KB role for ClinCase tenant ${var.organization_id} — querying S3 Vectors index."
}

data "aws_iam_policy_document" "bedrock_kb_inline" {
  # Read source documents (during embedding refresh)
  statement {
    sid       = "ReadSourceBucket"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      var.source_bucket_arn,
      "${var.source_bucket_arn}/*",
    ]
  }

  # Query the S3 Vectors index
  statement {
    sid     = "QueryThisIndex"
    effect  = "Allow"
    actions = [
      "s3vectors:QueryIndex",
      "s3vectors:DescribeIndex",
    ]
    resources = [aws_s3_vectors_index.policies.arn]
  }

  # KMS for encrypted source + index
  statement {
    sid     = "KMSDecryptForThisTenant"
    effect  = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
    ]
    resources = [var.kms_key_arn]
  }

  # Invoke the embedding model
  statement {
    sid     = "InvokeEmbeddingModel"
    effect  = "Allow"
    actions = ["bedrock:InvokeModel"]
    resources = [var.embedding_model_arn]
  }

  # Deny anything else, explicitly
  statement {
    sid       = "DenyEverythingElse"
    effect    = "Deny"
    actions   = ["s3:DeleteObject", "s3:PutObject", "s3:DeleteBucket"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "bedrock_kb" {
  role   = aws_iam_role.bedrock_kb.id
  policy = data.aws_iam_policy_document.bedrock_kb_inline.json
}
