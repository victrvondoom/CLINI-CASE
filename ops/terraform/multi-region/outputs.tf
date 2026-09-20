# ─── Outputs consumed by the K8s deployment + ops dashboards ────────────────

output "primary_db_writer_endpoint" {
  description = "Connection endpoint for the writer (apps point DATABASE_URL here)."
  value       = aws_rds_cluster.primary.endpoint
}

output "primary_db_reader_endpoint" {
  description = "Read-replica endpoint within the primary cluster (cluster-level reader)."
  value       = aws_rds_cluster.primary.reader_endpoint
}

output "secondary_db_reader_endpoint" {
  description = "Reader endpoint in the secondary region. Apps in us-east-1 read from here."
  value       = aws_rds_cluster.secondary.reader_endpoint
}

output "global_cluster_arn" {
  description = "ARN of the Aurora Global cluster — used by failover automation."
  value       = aws_rds_global_cluster.clincase.arn
}

output "primary_kms_key_arn" {
  description = "Multi-region KMS key ARN. Bind IRSA roles to this for envelope encryption."
  value       = aws_kms_key.primary.arn
}

output "secondary_kms_key_arn" {
  description = "Replica KMS key ARN in the secondary region."
  value       = aws_kms_replica_key.secondary.arn
}

output "service_dns_name" {
  description = "Public DNS name (LBR) — set this in the K8s ingress per region."
  value       = var.service_dns_name
}

output "primary_audit_bucket_arn" {
  description = "Primary-region audit bucket ARN (writes go here)."
  value       = aws_s3_bucket.primary_audit.arn
}

output "secondary_audit_bucket_arn" {
  description = "Secondary-region audit bucket ARN (CRR replica)."
  value       = aws_s3_bucket.secondary_audit.arn
}

output "primary_health_check_id" {
  description = "Route 53 health check ID for the primary ALB. Wire to PagerDuty."
  value       = aws_route53_health_check.primary.id
}

output "secondary_health_check_id" {
  description = "Route 53 health check ID for the secondary ALB."
  value       = aws_route53_health_check.secondary.id
}
