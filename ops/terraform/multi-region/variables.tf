# ─── Input variables for multi-region module ────────────────────────────────

variable "primary_region" {
  description = "Primary AWS region for ClinCase (writer)."
  type        = string
  default     = "ap-south-1"
}

variable "secondary_region" {
  description = "Secondary AWS region for warm-standby + read-replica."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment tag (prod, staging, demo)."
  type        = string
  default     = "prod"
}

variable "cost_center" {
  description = "Cost center for chargeback."
  type        = string
  default     = "CLINCASE"
}

# --- RDS (Aurora Global) ----------------------------------------------------

variable "global_cluster_identifier" {
  description = "Cluster ID for the Aurora Global Database."
  type        = string
  default     = "clincase"
}

variable "engine_version" {
  description = "Aurora PostgreSQL engine version."
  type        = string
  default     = "15.4"
}

variable "primary_instance_class" {
  description = "Instance class for primary writer."
  type        = string
  default     = "db.r6g.xlarge" # 4 vCPU, 32 GB
}

variable "secondary_instance_class" {
  description = "Instance class for secondary reader (warm-standby)."
  type        = string
  default     = "db.r6g.large" # 2 vCPU, 16 GB — cheaper at idle
}

variable "primary_db_subnet_ids" {
  description = "VPC subnet IDs for the primary cluster (private subnets only)."
  type        = list(string)
}

variable "secondary_db_subnet_ids" {
  description = "VPC subnet IDs for the secondary cluster (private subnets only)."
  type        = list(string)
}

variable "primary_security_group_ids" {
  description = "Security group IDs for the primary cluster."
  type        = list(string)
}

variable "secondary_security_group_ids" {
  description = "Security group IDs for the secondary cluster."
  type        = list(string)
}

variable "master_username" {
  description = "Aurora master username (NOT used by app — app uses IAM auth)."
  type        = string
  default     = "clincase_admin"
}

variable "master_password" {
  description = "Aurora master password. Pulled from AWS Secrets Manager in production."
  type        = string
  sensitive   = true
}

variable "backup_retention_period_days" {
  description = "Aurora automatic backup retention. CMS-0057-F audit minimum: 7 years."
  type        = number
  default     = 35
}

variable "deletion_protection" {
  description = "Aurora deletion protection. ALWAYS true in production."
  type        = bool
  default     = true
}

# --- Route 53 ---------------------------------------------------------------

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID for the public ClinCase domain."
  type        = string
}

variable "service_dns_name" {
  description = "Public DNS name for the ClinCase API."
  type        = string
  default     = "api.clincase.example.com"
}

variable "primary_alb_dns_name" {
  description = "DNS name of the primary-region ALB (output of api-deployment.yaml)."
  type        = string
}

variable "primary_alb_zone_id" {
  description = "Hosted zone ID of the primary-region ALB."
  type        = string
}

variable "secondary_alb_dns_name" {
  description = "DNS name of the secondary-region ALB."
  type        = string
}

variable "secondary_alb_zone_id" {
  description = "Hosted zone ID of the secondary-region ALB."
  type        = string
}

# --- S3 cross-region replication --------------------------------------------

variable "primary_audit_bucket" {
  description = "S3 bucket name in primary region for agent_runs / appeals export."
  type        = string
  default     = "clincase-audit-aps1"
}

variable "secondary_audit_bucket" {
  description = "S3 bucket name in secondary region for replicated audit data."
  type        = string
  default     = "clincase-audit-use1"
}
