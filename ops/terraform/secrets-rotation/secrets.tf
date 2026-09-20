resource "aws_kms_key" "secrets" {
  description             = "KMS key for ClinCase secrets (rotation-managed)"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/clincase-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# -----------------------------------------------------------------------------
# 1) JWT secret — application-level. The rotation Lambda implements the
#    "two-secret" overlap pattern (described in README.md).
# -----------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "jwt_secret" {
  name        = "clincase/jwt-secret"
  description = "HS256 signing key for ClinCase JWTs. Auto-rotated every ${var.jwt_rotation_days}d."
  kms_key_id  = aws_kms_key.secrets.arn

  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_rotation" "jwt_secret" {
  secret_id           = aws_secretsmanager_secret.jwt_secret.id
  rotation_lambda_arn = aws_lambda_function.rotate_jwt.arn

  rotation_rules {
    automatically_after_days = var.jwt_rotation_days
  }
}

# -----------------------------------------------------------------------------
# 2) Postgres master credential — AWS-provided rotation Lambda
# -----------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "postgres_master" {
  name        = "clincase/postgres-master"
  description = "Aurora master credentials. Auto-rotated every ${var.postgres_rotation_days}d."
  kms_key_id  = aws_kms_key.secrets.arn
}

resource "aws_secretsmanager_secret_rotation" "postgres_master" {
  secret_id           = aws_secretsmanager_secret.postgres_master.id
  rotation_lambda_arn = aws_lambda_function.rotate_postgres.arn

  rotation_rules {
    automatically_after_days = var.postgres_rotation_days
  }
}

# -----------------------------------------------------------------------------
# 3) Bedrock IAM access key — for the GenAI Gateway's underlying client.
#    Recommended: use IRSA + STS instead of long-lived keys. This is a
#    fallback for environments that can't use IRSA.
# -----------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "bedrock_iam_key" {
  name        = "clincase/bedrock-iam-key"
  description = "Bedrock IAM access key. Auto-rotated every ${var.bedrock_iam_key_rotation_days}d."
  kms_key_id  = aws_kms_key.secrets.arn
}

resource "aws_secretsmanager_secret_rotation" "bedrock_iam_key" {
  secret_id           = aws_secretsmanager_secret.bedrock_iam_key.id
  rotation_lambda_arn = aws_lambda_function.rotate_iam_key.arn

  rotation_rules {
    automatically_after_days = var.bedrock_iam_key_rotation_days
  }
}
