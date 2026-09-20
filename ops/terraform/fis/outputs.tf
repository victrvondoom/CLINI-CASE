output "experiment_template_ids" {
  description = "FIS template IDs. Consumed by ops/sre/scripts/chaos.sh."
  value = {
    "EXP-01" = aws_fis_experiment_template.exp_01_bedrock_throttle_proxy.id
    "EXP-02" = aws_fis_experiment_template.exp_02_pod_kill.id
    "EXP-03" = aws_fis_experiment_template.exp_03_rds_failover.id
    "EXP-04" = aws_fis_experiment_template.exp_04_redis_failover.id
  }
}

output "fis_execution_role_arn" {
  value = aws_iam_role.fis_execution.arn
}
