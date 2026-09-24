variable "aws_region" {
  description = "Region the VPC + EKS cluster live in."
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "cost_center" {
  type    = string
  default = "CLINCASE-PROD"
}

# --- Network topology -------------------------------------------------------

variable "vpc_id" {
  description = "VPC the ClinCase EKS cluster runs in."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs across multiple AZs (interface endpoint goes in each)."
  type        = list(string)
}

variable "eks_node_security_group_id" {
  description = "Security group attached to EKS worker nodes — only this SG can talk to the endpoint."
  type        = string
}

# --- EKS cluster identity ---------------------------------------------------

variable "eks_cluster_name" {
  description = "EKS cluster name. Used to scope the IRSA trust policy."
  type        = string
}

variable "k8s_namespace" {
  description = "Kubernetes namespace the clincase pods run in."
  type        = string
  default     = "clincase"
}

variable "k8s_service_accounts" {
  description = "K8s ServiceAccount names that should assume the Bedrock invoke role."
  type        = list(string)
  default     = ["clincase-api", "clincase-worker"]
}

# --- Bedrock allowlist ------------------------------------------------------

variable "allowed_model_arns" {
  description = "Bedrock model ARNs the app is permitted to invoke. ANY new model requires a Terraform change."
  type        = list(string)
}

variable "guardrail_arn" {
  description = "Per-tenant Bedrock Guardrail ARN. Empty string disables guardrail enforcement at IAM (still active in code)."
  type        = string
  default     = ""
}

# --- CloudWatch Logs --------------------------------------------------------

variable "model_invocation_log_retention_days" {
  description = "Bedrock model invocation log retention. CMS-0057-F § IV.D minimum is 7 years (2557d)."
  type        = number
  default     = 2557
}
