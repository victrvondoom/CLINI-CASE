# ─── Aurora Global Database (cross-region replica) ──────────────────────────
# One global cluster → primary cluster (writer) in ap-south-1 + secondary
# cluster (reader) in us-east-1. The secondary can be promoted to primary
# in ~60-90s during a regional failover (RPO ~1s). All writes go to the
# primary; reads can be served from either region.
#
# Storage encryption is non-negotiable for HIPAA: aws_kms_key per region,
# bound to a multi-region KMS key alias so envelope-encrypted data stays
# decryptable on either side.

# --- KMS keys (multi-region) ------------------------------------------------

resource "aws_kms_key" "primary" {
  provider                = aws.primary
  description             = "ClinCase Aurora primary-region encryption (multi-region key)"
  enable_key_rotation     = true
  multi_region            = true
  deletion_window_in_days = 30
  tags                    = { Tier = "data", Compliance = "HIPAA" }
}

resource "aws_kms_replica_key" "secondary" {
  provider                = aws.secondary
  description             = "ClinCase Aurora secondary-region encryption (replica)"
  primary_key_arn         = aws_kms_key.primary.arn
  deletion_window_in_days = 30
  tags                    = { Tier = "data", Compliance = "HIPAA" }
}

# --- Global cluster ---------------------------------------------------------

resource "aws_rds_global_cluster" "clincase" {
  provider                  = aws.primary
  global_cluster_identifier = var.global_cluster_identifier
  engine                    = "aurora-postgresql"
  engine_version            = var.engine_version
  database_name             = "clincase"
  storage_encrypted         = true
  deletion_protection       = var.deletion_protection
}

# --- Primary cluster (ap-south-1) -------------------------------------------

resource "aws_rds_cluster" "primary" {
  provider                        = aws.primary
  cluster_identifier              = "${var.global_cluster_identifier}-primary"
  engine                          = aws_rds_global_cluster.clincase.engine
  engine_version                  = aws_rds_global_cluster.clincase.engine_version
  global_cluster_identifier       = aws_rds_global_cluster.clincase.id
  master_username                 = var.master_username
  master_password                 = var.master_password
  database_name                   = "clincase"
  db_subnet_group_name            = aws_db_subnet_group.primary.name
  vpc_security_group_ids          = var.primary_security_group_ids
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.primary.arn
  iam_database_authentication_enabled = true
  backup_retention_period         = var.backup_retention_period_days
  preferred_backup_window         = "20:00-21:00" # UTC = 01:30 IST
  preferred_maintenance_window    = "sun:21:00-sun:22:00"
  enabled_cloudwatch_logs_exports = ["postgresql"]
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = false
  final_snapshot_identifier       = "clincase-primary-final"
  apply_immediately               = false
  copy_tags_to_snapshot           = true
}

resource "aws_rds_cluster_instance" "primary_writer" {
  provider             = aws.primary
  identifier           = "${var.global_cluster_identifier}-primary-1"
  cluster_identifier   = aws_rds_cluster.primary.id
  instance_class       = var.primary_instance_class
  engine               = aws_rds_cluster.primary.engine
  engine_version       = aws_rds_cluster.primary.engine_version
  db_subnet_group_name = aws_db_subnet_group.primary.name
  publicly_accessible  = false
  apply_immediately    = false
  performance_insights_enabled = true
  monitoring_interval  = 60
}

resource "aws_db_subnet_group" "primary" {
  provider   = aws.primary
  name       = "${var.global_cluster_identifier}-primary"
  subnet_ids = var.primary_db_subnet_ids
}

# --- Secondary cluster (us-east-1) ------------------------------------------

resource "aws_rds_cluster" "secondary" {
  provider                            = aws.secondary
  cluster_identifier                  = "${var.global_cluster_identifier}-secondary"
  engine                              = aws_rds_global_cluster.clincase.engine
  engine_version                      = aws_rds_global_cluster.clincase.engine_version
  global_cluster_identifier           = aws_rds_global_cluster.clincase.id
  db_subnet_group_name                = aws_db_subnet_group.secondary.name
  vpc_security_group_ids              = var.secondary_security_group_ids
  storage_encrypted                   = true
  kms_key_id                          = aws_kms_replica_key.secondary.arn
  iam_database_authentication_enabled = true
  enabled_cloudwatch_logs_exports     = ["postgresql"]
  deletion_protection                 = var.deletion_protection
  skip_final_snapshot                 = false
  final_snapshot_identifier           = "clincase-secondary-final"
  apply_immediately                   = false

  # Wait for primary to exist before joining the global cluster.
  depends_on = [aws_rds_cluster_instance.primary_writer]

  lifecycle {
    # Once joined to a global cluster, secondaries don't accept some
    # parameters that are inherited from the primary. Ignore drift on those.
    ignore_changes = [
      replication_source_identifier,
      master_username,
      master_password,
    ]
  }
}

resource "aws_rds_cluster_instance" "secondary_reader" {
  provider             = aws.secondary
  identifier           = "${var.global_cluster_identifier}-secondary-1"
  cluster_identifier   = aws_rds_cluster.secondary.id
  instance_class       = var.secondary_instance_class
  engine               = aws_rds_cluster.secondary.engine
  engine_version       = aws_rds_cluster.secondary.engine_version
  db_subnet_group_name = aws_db_subnet_group.secondary.name
  publicly_accessible  = false
  performance_insights_enabled = true
  monitoring_interval  = 60
}

resource "aws_db_subnet_group" "secondary" {
  provider   = aws.secondary
  name       = "${var.global_cluster_identifier}-secondary"
  subnet_ids = var.secondary_db_subnet_ids
}
