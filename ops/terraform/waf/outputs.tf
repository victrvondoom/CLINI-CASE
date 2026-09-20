output "wacl_arn" {
  description = "WACL ARN — pass to additional ALB or CloudFront associations."
  value       = aws_wafv2_web_acl.clincase.arn
}

output "wacl_name" {
  value = aws_wafv2_web_acl.clincase.name
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.waf_logs.name
}
