# ─── Outputs ────────────────────────────────────────────────────────────────

output "sonnet_primary_arn" {
  description = "ARN of the Sonnet provisioned-throughput resource in the primary region."
  value       = aws_bedrock_provisioned_model_throughput.sonnet_primary.provisioned_model_arn
}

output "haiku_primary_arn" {
  description = "ARN of the Haiku provisioned-throughput resource in the primary region."
  value       = aws_bedrock_provisioned_model_throughput.haiku_primary.provisioned_model_arn
}

output "sonnet_secondary_arn" {
  description = "ARN of the Sonnet provisioned-throughput resource in the secondary region. Empty when enable_secondary_region=false."
  value       = try(aws_bedrock_provisioned_model_throughput.sonnet_secondary[0].provisioned_model_arn, "")
}

output "haiku_secondary_arn" {
  description = "ARN of the Haiku provisioned-throughput resource in the secondary region. Empty when enable_secondary_region=false."
  value       = try(aws_bedrock_provisioned_model_throughput.haiku_secondary[0].provisioned_model_arn, "")
}

output "alarm_arns" {
  description = "All CloudWatch alarm ARNs created by this module."
  value = {
    sonnet_p3 = aws_cloudwatch_metric_alarm.sonnet_p3.arn
    sonnet_p2 = aws_cloudwatch_metric_alarm.sonnet_p2.arn
    haiku_p3  = aws_cloudwatch_metric_alarm.haiku_p3.arn
  }
}
