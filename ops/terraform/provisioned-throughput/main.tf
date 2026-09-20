# ─── Bedrock Provisioned Throughput ──────────────────────────────────────────
# Locks predictable LLM capacity at a fixed monthly cost. Replaces on-demand
# billing for the Production / Scale tiers in ops/SCALING.md. Apply this
# *before* a payer go-live event so the warmed throughput is ready Day 1.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
  backend "s3" {
    encrypt        = true
    dynamodb_table = "clincase-tfstate-locks"
  }
}

provider "aws" {
  alias  = "primary"
  region = var.primary_region
  default_tags {
    tags = {
      Project     = "ClinCase"
      Component   = "bedrock-provisioned"
      Environment = var.environment
      ManagedBy   = "terraform"
      CostCenter  = var.cost_center
    }
  }
}

provider "aws" {
  alias  = "secondary"
  region = var.secondary_region
  default_tags {
    tags = {
      Project     = "ClinCase"
      Component   = "bedrock-provisioned"
      Environment = var.environment
      ManagedBy   = "terraform"
      CostCenter  = var.cost_center
    }
  }
}
