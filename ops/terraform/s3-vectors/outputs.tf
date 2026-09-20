output "vectors_index_arn" {
  description = "S3 Vectors index ARN. Pass this to Bedrock KB config as the vectorStore."
  value       = aws_s3_vectors_index.policies.arn
}

output "vectors_index_name" {
  description = "Index name (per-tenant)."
  value       = aws_s3_vectors_index.policies.name
}

output "bedrock_kb_role_arn" {
  description = "IAM role ARN Bedrock KB assumes when querying this index. Configure on the Bedrock KB resource."
  value       = aws_iam_role.bedrock_kb.arn
}
