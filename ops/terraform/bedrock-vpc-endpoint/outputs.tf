output "bedrock_runtime_endpoint_id" {
  description = "VPC endpoint ID for bedrock-runtime."
  value       = aws_vpc_endpoint.bedrock_runtime.id
}

output "bedrock_agent_runtime_endpoint_id" {
  description = "VPC endpoint ID for bedrock-agent-runtime."
  value       = aws_vpc_endpoint.bedrock_agent_runtime.id
}

output "bedrock_invoke_role_arn" {
  description = "IRSA role ARN — annotate the K8s ServiceAccounts with this."
  value       = aws_iam_role.bedrock_invoke.arn
}

output "bedrock_logging_role_arn" {
  description = "Role for Bedrock service to write model-invocation logs."
  value       = aws_iam_role.bedrock_logging.arn
}

output "bedrock_invocations_log_group_name" {
  description = "CloudWatch Logs group for Bedrock model invocations (CMS-0057-F § IV.D evidence)."
  value       = aws_cloudwatch_log_group.bedrock_invocations.name
}

output "vpce_security_group_id" {
  description = "Security group attached to both VPC endpoints."
  value       = aws_security_group.bedrock_vpce.id
}
