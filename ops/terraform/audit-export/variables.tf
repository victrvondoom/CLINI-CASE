variable "aws_region" {
  type        = string
  default     = "ap-south-1"
  description = "Region the customer's stream lives in. Must match the cell region for low-latency replication."
}

variable "environment" {
  type        = string
  default     = "prod"
  description = "Environment tag (prod / staging / dev)."
}

variable "tenant_id" {
  type        = string
  description = "ClinCase organization_id. e.g. 'org_humana'. Used to namespace all resources."
}

variable "customer_account_id" {
  type        = string
  description = "AWS account ID of the customer. They will assume the role we create here."
  validation {
    condition     = length(regexall("^[0-9]{12}$", var.customer_account_id)) > 0
    error_message = "customer_account_id must be a 12-digit AWS account ID."
  }
}

variable "customer_external_id" {
  type        = string
  sensitive   = true
  description = "External ID for the cross-account role (mitigates confused-deputy). Generate fresh per-tenant via `openssl rand -hex 16`."
  validation {
    condition     = length(var.customer_external_id) >= 16
    error_message = "external_id must be at least 16 characters."
  }
}

variable "retention_days" {
  type        = number
  default     = 90
  description = "CloudWatch Logs retention. Customer is the system of record for >90d."
}

variable "kinesis_shard_count" {
  type        = number
  default     = 1
  description = "Per-tenant shard count. 1 shard handles ~1MB/s ingest — sufficient up to ~1000 cases/day per tenant."
}
