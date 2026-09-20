variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "rds_cluster_arn" {
  type        = string
  description = "Aurora cluster ARN that DATABASE_URL points at. Required for Postgres rotation."
}

variable "vpc_subnet_ids" {
  type        = list(string)
  description = "Private subnets the rotation Lambdas run in (must reach RDS / Bedrock VPC endpoint)."
}

variable "vpc_security_group_ids" {
  type        = list(string)
  description = "Security group(s) for the rotation Lambdas."
}

variable "jwt_rotation_days" {
  type    = number
  default = 30
}

variable "postgres_rotation_days" {
  type    = number
  default = 30
}

variable "bedrock_iam_key_rotation_days" {
  type    = number
  default = 90
}
