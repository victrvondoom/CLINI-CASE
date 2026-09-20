# =============================================================================
# AWS DMS — Aurora source → Kinesis target replication task
# =============================================================================

resource "aws_dms_replication_subnet_group" "clincase" {
  replication_subnet_group_id          = "clincase-cdc-subnet-group"
  replication_subnet_group_description = "ClinCase DMS subnet group (private subnets only)"
  subnet_ids                           = var.vpc_subnet_ids
}

resource "aws_dms_replication_instance" "clincase" {
  replication_instance_id     = "clincase-cdc"
  replication_instance_class  = "dms.t3.medium"
  allocated_storage           = 50
  auto_minor_version_upgrade  = true
  multi_az                    = false # bump to true for Gold-tier customers
  publicly_accessible         = false
  vpc_security_group_ids      = var.security_group_ids
  replication_subnet_group_id = aws_dms_replication_subnet_group.clincase.replication_subnet_group_id
  kms_key_arn                 = var.kms_key_arn
  preferred_maintenance_window = "sun:21:00-sun:22:00"
  apply_immediately           = false
}

# Source: Aurora Postgres
resource "aws_dms_endpoint" "aurora_source" {
  endpoint_id   = "clincase-aurora-source"
  endpoint_type = "source"
  engine_name   = "aurora-postgresql"

  server_name   = var.aurora_endpoint
  port          = var.aurora_port
  database_name = var.aurora_database
  username      = var.aurora_username
  password      = jsondecode(data.aws_secretsmanager_secret_version.dms_pw.secret_string).password

  ssl_mode = "require"
  kms_key_arn = var.kms_key_arn
}

data "aws_secretsmanager_secret_version" "dms_pw" {
  secret_id = var.aurora_password_secret_arn
}

# Target: Kinesis
resource "aws_dms_endpoint" "kinesis_target" {
  endpoint_id   = "clincase-kinesis-target"
  endpoint_type = "target"
  engine_name   = "kinesis"

  kinesis_settings {
    stream_arn               = aws_kinesis_stream.clincase_cdc.arn
    message_format           = "json"
    service_access_role_arn  = aws_iam_role.dms_to_kinesis.arn
    include_partition_value  = true
    partition_include_schema_table = true
    include_null_and_empty   = false
    include_table_alter_operations = true
  }
}

resource "aws_dms_replication_task" "clincase_to_kinesis" {
  replication_task_id      = "clincase-postgres-to-kinesis"
  migration_type           = "full-load-and-cdc"
  replication_instance_arn = aws_dms_replication_instance.clincase.replication_instance_arn
  source_endpoint_arn      = aws_dms_endpoint.aurora_source.endpoint_arn
  target_endpoint_arn      = aws_dms_endpoint.kinesis_target.endpoint_arn

  table_mappings = jsonencode({
    rules = [
      for idx, t in var.captured_tables : {
        rule-type   = "selection"
        rule-id     = tostring(idx + 1)
        rule-name   = "include-${t}"
        object-locator = {
          schema-name = "public"
          table-name  = t
        }
        rule-action = "include"
      }
    ]
  })

  replication_task_settings = jsonencode({
    Logging = {
      EnableLogging = true
      LogComponents = [
        { Id = "DATA_STRUCTURE", Severity = "LOGGER_SEVERITY_INFO" },
        { Id = "TRANSFORMATION", Severity = "LOGGER_SEVERITY_INFO" },
      ]
    }
    StreamBufferSettings = {
      StreamBufferCount  = 3
      StreamBufferSizeInMB = 8
    }
  })

  start_replication_task = true
  tags = { Name = "clincase-cdc-task" }
}

# IAM role DMS uses to write to Kinesis
resource "aws_iam_role" "dms_to_kinesis" {
  name = "clincase-dms-to-kinesis"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "dms.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "dms_to_kinesis" {
  role = aws_iam_role.dms_to_kinesis.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["kinesis:PutRecord", "kinesis:PutRecords", "kinesis:DescribeStream"]
      Resource = aws_kinesis_stream.clincase_cdc.arn
    }]
  })
}
