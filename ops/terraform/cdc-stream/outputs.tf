output "cdc_lake_bucket_arn" {
  description = "S3 audit-lake bucket. Athena queries land here."
  value       = aws_s3_bucket.cdc_lake.arn
}

output "kinesis_stream_arn" {
  description = "Kinesis Data Stream ARN. Other consumers can also subscribe."
  value       = aws_kinesis_stream.clincase_cdc.arn
}

output "glue_database_name" {
  value = aws_glue_catalog_database.clincase_audit.name
}

output "athena_workgroup_name" {
  value = aws_athena_workgroup.clincase_audit.name
}

output "dms_replication_task_arn" {
  value = aws_dms_replication_task.clincase_to_kinesis.replication_task_arn
}
