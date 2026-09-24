# ─── Inputs for Bedrock provisioned-throughput module ───────────────────────

variable "primary_region" {
  description = "Primary AWS region for ClinCase (Mumbai by default)."
  type        = string
  default     = "ap-south-1"
}

variable "secondary_region" {
  description = "Secondary region — optional, gated by enable_secondary_region."
  type        = string
  default     = "us-east-1"
}

variable "enable_secondary_region" {
  description = "Provision throughput in the secondary region too. Doubles cost; only enable when paired with the multi-region module."
  type        = bool
  default     = false
}

variable "environment" {
  description = "Environment tag (prod, staging)."
  type        = string
  default     = "prod"
}

variable "cost_center" {
  description = "Cost center for chargeback."
  type        = string
  default     = "CLINCASE-PROD"
}

# --- Model IDs --------------------------------------------------------------

variable "sonnet_model_id" {
  description = "Bedrock model ID for Sonnet (per-region inference profile)."
  type        = string
  default     = "apac.anthropic.claude-sonnet-4-6-20251022-v1:0"
}

variable "haiku_model_id" {
  description = "Bedrock model ID for Haiku."
  type        = string
  default     = "apac.anthropic.claude-haiku-4-5-20251001-v1:0"
}

# --- Capacity ---------------------------------------------------------------
# Each "model unit" (MU) provides bounded TPM. Verify the per-MU number on
# the AWS Bedrock console before sizing — Anthropic publishes this under
# "Provisioned throughput" → model details.

variable "sonnet_model_units_primary" {
  description = "MU of Sonnet to provision in the primary region."
  type        = number
  default     = 1

  validation {
    condition     = var.sonnet_model_units_primary >= 0 && var.sonnet_model_units_primary <= 100
    error_message = "Sonnet MU must be between 0 and 100; if you need more contact AWS quotas first."
  }
}

variable "haiku_model_units_primary" {
  description = "MU of Haiku to provision in the primary region."
  type        = number
  default     = 1
}

variable "sonnet_model_units_secondary" {
  description = "MU of Sonnet to provision in the secondary region (only when enable_secondary_region=true)."
  type        = number
  default     = 1
}

variable "haiku_model_units_secondary" {
  description = "MU of Haiku to provision in the secondary region (only when enable_secondary_region=true)."
  type        = number
  default     = 1
}

# --- Commitment tier --------------------------------------------------------
# AWS Bedrock supports three commitment tiers:
#   • "" / null    — no commit (most flexible, most expensive)
#   • "OneMonth"   — 1-month commit (~30% discount)
#   • "SixMonths"  — 6-month commit (~51% discount)
# For a first customer pilot, OneMonth is the right call.

variable "commitment_duration" {
  description = "Bedrock provisioned-throughput commitment tier. Empty string = no commit."
  type        = string
  default     = "OneMonth"

  validation {
    condition     = contains(["", "OneMonth", "SixMonths"], var.commitment_duration)
    error_message = "commitment_duration must be one of '', 'OneMonth', 'SixMonths'."
  }
}

# --- CloudWatch alarms ------------------------------------------------------

variable "alarm_sns_topic_arn" {
  description = "SNS topic that PagerDuty subscribes to for alarm fan-out."
  type        = string
}

variable "utilization_p3_threshold" {
  description = "Utilization % above which a P3 alarm fires."
  type        = number
  default     = 80
}

variable "utilization_p2_threshold" {
  description = "Utilization % above which a P2 alarm fires (closer to capacity exhaustion)."
  type        = number
  default     = 95
}
