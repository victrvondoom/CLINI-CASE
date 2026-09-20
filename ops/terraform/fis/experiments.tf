# =============================================================================
# 5 chaos-experiment templates — see ops/sre/CHAOS_ENGINEERING.md for hypotheses
# =============================================================================

locals {
  common_stop_condition = {
    source = "aws:cloudwatch:alarm"
    value  = var.stop_condition_alarm_arn
  }
  common_log_config = {
    cloud_watch_logs_configuration = {
      log_group_arn = var.fis_log_group_arn
    }
    log_schema_version = 2
  }
}

# -----------------------------------------------------------------------------
# EXP-02 — Worker pod kill (the simplest one to verify FIS is wired)
# -----------------------------------------------------------------------------
resource "aws_fis_experiment_template" "exp_02_pod_kill" {
  description = "EXP-02: Kill an ClinCase worker pod 30s after start. Verify janitor reaps + requeues."
  role_arn    = aws_iam_role.fis_execution.arn

  stop_condition { source = local.common_stop_condition.source; value = local.common_stop_condition.value }

  action {
    name      = "kill-worker-pod"
    action_id = "aws:eks:terminate-nodegroup-instances"
    parameter { key = "instanceTerminationPercentage"; value = "10" }
    target { key = "Nodegroups"; value = "worker-nodegroup" }
  }

  target {
    name           = "worker-nodegroup"
    resource_type  = "aws:eks:nodegroup"
    selection_mode = "ALL"
    resource_tag {
      key   = "Project"
      value = "ClinCase"
    }
  }

  log_configuration {
    log_schema_version = 2
    cloudwatch_logs_configuration { log_group_arn = var.fis_log_group_arn }
  }

  tags = { Name = "EXP-02-pod-kill", Severity = "low" }
}

# -----------------------------------------------------------------------------
# EXP-03 — RDS Aurora primary failover
# -----------------------------------------------------------------------------
resource "aws_fis_experiment_template" "exp_03_rds_failover" {
  description = "EXP-03: Force RDS Aurora primary failover. Verify <60s reconnect."
  role_arn    = aws_iam_role.fis_execution.arn

  stop_condition { source = local.common_stop_condition.source; value = local.common_stop_condition.value }

  action {
    name      = "force-failover"
    action_id = "aws:rds:failover-db-cluster"
    target { key = "Clusters"; value = "clincase-cluster" }
  }

  target {
    name           = "clincase-cluster"
    resource_type  = "aws:rds:cluster"
    selection_mode = "ALL"
    resource_arns  = ["arn:aws:rds:${var.aws_region}:${data.aws_caller_identity.current.account_id}:cluster:${var.rds_cluster_id}"]
  }

  log_configuration {
    log_schema_version = 2
    cloudwatch_logs_configuration { log_group_arn = var.fis_log_group_arn }
  }

  tags = { Name = "EXP-03-rds-failover", Severity = "medium" }
}

# -----------------------------------------------------------------------------
# EXP-04 — ElastiCache (Redis) primary failover
# -----------------------------------------------------------------------------
resource "aws_fis_experiment_template" "exp_04_redis_failover" {
  description = "EXP-04: Force ElastiCache Redis primary failover. Verify SSE pub/sub degrades soft."
  role_arn    = aws_iam_role.fis_execution.arn

  stop_condition { source = local.common_stop_condition.source; value = local.common_stop_condition.value }

  action {
    name      = "redis-failover"
    action_id = "aws:elasticache:replicationgroup-interrupt-az-power"
    parameter { key = "duration"; value = "PT5M" }
    target { key = "ReplicationGroups"; value = "clincase-redis" }
  }

  target {
    name           = "clincase-redis"
    resource_type  = "aws:elasticache:replicationgroup"
    selection_mode = "ALL"
    resource_arns  = ["arn:aws:elasticache:${var.aws_region}:${data.aws_caller_identity.current.account_id}:replicationgroup:${var.redis_replication_group_id}"]
  }

  log_configuration {
    log_schema_version = 2
    cloudwatch_logs_configuration { log_group_arn = var.fis_log_group_arn }
  }

  tags = { Name = "EXP-04-redis-failover", Severity = "medium" }
}

# -----------------------------------------------------------------------------
# EXP-01 (Bedrock 5xx storm) and EXP-05 (TriZetto block) intentionally use
# AWS SSM documents instead of native FIS actions — Bedrock fault injection
# isn't a FIS-supported action type as of mid-2026 (we use SSM to scale
# workers to 0 for the same effect).
# -----------------------------------------------------------------------------

resource "aws_fis_experiment_template" "exp_01_bedrock_throttle_proxy" {
  description = "EXP-01 (proxy): Scale workers to 0 for 5min to simulate Bedrock unavailability customer-side."
  role_arn    = aws_iam_role.fis_execution.arn

  stop_condition { source = local.common_stop_condition.source; value = local.common_stop_condition.value }

  action {
    name      = "scale-workers-to-zero"
    action_id = "aws:ssm:start-automation-execution"
    parameter { key = "documentArn"; value = "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript" }
    parameter {
      key   = "documentParameters"
      value = jsonencode({
        commands = [
          "kubectl scale deploy/clincase-worker -n clincase --replicas=0",
          "sleep 300",
          "kubectl scale deploy/clincase-worker -n clincase --replicas=5",
        ]
      })
    }
    parameter { key = "maxDuration"; value = "PT10M" }
    target { key = "Instances"; value = "controller-instance" }
  }

  target {
    name           = "controller-instance"
    resource_type  = "aws:ec2:instance"
    selection_mode = "COUNT(1)"
    resource_tag {
      key   = "Role"
      value = "ChaosController"
    }
  }

  log_configuration {
    log_schema_version = 2
    cloudwatch_logs_configuration { log_group_arn = var.fis_log_group_arn }
  }

  tags = { Name = "EXP-01-bedrock-throttle-proxy", Severity = "medium" }
}
