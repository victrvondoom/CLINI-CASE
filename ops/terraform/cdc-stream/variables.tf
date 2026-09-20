variable "aws_region" { type = string; default = "ap-south-1" }
variable "environment" { type = string; default = "prod" }
variable "cost_center" { type = string; default = "AEROFYTA-CLINCASE-PROD" }

# Aurora source
variable "aurora_endpoint"   { type = string }
variable "aurora_port"       { type = number; default = 5432 }
variable "aurora_database"   { type = string; default = "clincase" }
variable "aurora_username"   { type = string; default = "clincase_dms" }
variable "aurora_password_secret_arn" {
  description = "Secrets Manager ARN holding the DMS user password."
  type        = string
}

# Networking — DMS instance lives in the same VPC as Aurora
variable "vpc_subnet_ids"       { type = list(string) }
variable "security_group_ids"   { type = list(string) }
variable "kms_key_arn"          { type = string }

# Tables to capture (one Glue table per Postgres table)
variable "captured_tables" {
  type    = list(string)
  default = [
    "cases",
    "decisions",
    "appeals",
    "agent_runs",
    "reviewer_actions",
    "event_outbox",
    "llm_invocations",
  ]
}

# Audit lake retention
variable "lake_retention_days" {
  description = "S3 lifecycle: STANDARD → IA at 90d, IA → GLACIER at 180d, expire at this many days."
  type        = number
  default     = 2557 # 7 years (CMS-0057-F § IV.D minimum)
}
