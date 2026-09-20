variable "aws_region"         { type = string; default = "ap-south-1" }
variable "environment"        { type = string; default = "staging" }   # NEVER prod by default
variable "eks_cluster_name"   { type = string }
variable "rds_cluster_id"     { type = string }
variable "redis_replication_group_id" { type = string }

# Egress NACL ID for the EXP-05 (TriZetto block) experiment
variable "private_subnet_nacl_id" { type = string }

# CloudWatch alarm ARN that AUTO-STOPS any experiment if customer impact crosses threshold
variable "stop_condition_alarm_arn" {
  description = "Alarm that, when triggered, stops the in-flight FIS experiment immediately."
  type        = string
}

# Log group for FIS experiment lifecycle events
variable "fis_log_group_arn" {
  description = "CloudWatch Log group ARN for FIS experiment events."
  type        = string
}
