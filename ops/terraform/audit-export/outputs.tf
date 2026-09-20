output "kinesis_stream_arn" {
  description = "Per-tenant Kinesis stream the customer's SIEM consumes."
  value       = aws_kinesis_stream.tenant_audit_export.arn
}

output "tenant_consumer_role_arn" {
  description = "ARN the customer's account assumes from THEIR side."
  value       = aws_iam_role.tenant_consumer.arn
}

output "external_id" {
  description = "External ID the customer must put in their AssumeRole call. Treat as secret."
  sensitive   = true
  value       = var.customer_external_id
}

output "log_group_name" {
  description = "CloudWatch log group that ClinCase writes per-tenant audit events to."
  value       = aws_cloudwatch_log_group.tenant_audit.name
}

output "kms_key_arn" {
  description = "KMS CMK encrypting the per-tenant audit data."
  value       = aws_kms_key.tenant_audit.arn
}

output "onboarding_summary" {
  description = "Customer-facing summary."
  value = {
    tenant_id                  = var.tenant_id
    consumer_role_arn          = aws_iam_role.tenant_consumer.arn
    kinesis_stream_arn         = aws_kinesis_stream.tenant_audit_export.arn
    customer_must_provide_role = "in their account, with sts:AssumeRole on the consumer_role_arn above + sts:ExternalId matching the (sensitive) external_id"
    next_step                  = "Subscribe customer's Splunk Connect for Kinesis / AWS Sentinel / Chronicle to the kinesis_stream_arn"
  }
}
