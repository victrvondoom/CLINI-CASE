variable "aws_region" { type = string; default = "ap-south-1" }
variable "environment" { type = string; default = "prod" }
variable "alb_arn" {
  description = "ARN of the ClinCase ALB (output of ops/k8s/api-deployment.yaml's Ingress)."
  type        = string
}
variable "log_retention_days" { type = number; default = 90 }

variable "rate_limit_per_5min_bronze" { type = number; default = 3000 }   # ~10 r/s
variable "rate_limit_per_5min_silver" { type = number; default = 15000 }  # ~50 r/s
variable "rate_limit_per_5min_gold"   { type = number; default = 60000 }  # ~200 r/s

variable "blocked_request_alarm_sns_topic_arn" {
  description = "SNS topic for blocked-request anomaly alarm (PagerDuty)."
  type        = string
}
