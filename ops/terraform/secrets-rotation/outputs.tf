output "jwt_secret_arn" {
  description = "ARN of the auto-rotating JWT signing secret."
  value       = aws_secretsmanager_secret.jwt_secret.arn
}

output "postgres_master_secret_arn" {
  description = "ARN of the auto-rotating Postgres master credential."
  value       = aws_secretsmanager_secret.postgres_master.arn
}

output "bedrock_iam_key_secret_arn" {
  description = "ARN of the auto-rotating Bedrock IAM access key (fallback for non-IRSA environments)."
  value       = aws_secretsmanager_secret.bedrock_iam_key.arn
}

output "rotation_summary" {
  description = "Compliance summary."
  value = {
    jwt              = "${var.jwt_rotation_days}d rotation, two-secret overlap"
    postgres         = "${var.postgres_rotation_days}d rotation, AWS-managed Lambda"
    bedrock_iam_key  = "${var.bedrock_iam_key_rotation_days}d rotation"
    compliance       = "HIPAA § 164.308(a)(5)(ii)(D), NIST 800-53 IA-5, SOC 2 CC6.1"
  }
}
