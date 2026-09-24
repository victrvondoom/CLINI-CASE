# ─── ClinCase multi-region root ──────────────────────────────────────────────
# Two-region active/active. Primary in ap-south-1, secondary in us-east-1.
# Single Terraform state file (S3 + DynamoDB lock) drives both regions via
# provider aliases. Apply this from a workstation that has both regions'
# credentials configured (or via cross-account assume-role, if separate accts).
#
# WHY a single root and not two regional roots: the cross-region resources
# (Route 53 LBR, RDS Global Database, S3 CRR rule) MUST live in one state
# so Terraform can wire the providers correctly. Splitting per region creates
# a chicken-and-egg with the global cluster ARN.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
  backend "s3" {
    # Backend config is supplied at init time via -backend-config flags
    # so the bucket name doesn't get hardcoded into version control.
    encrypt        = true
    dynamodb_table = "clincase-tfstate-locks"
  }
}

# Primary region — Mumbai. Default Bedrock home for India ops + lowest
# latency to partner health-sciences clouds in BLR/HYD.
provider "aws" {
  alias  = "primary"
  region = var.primary_region
  default_tags {
    tags = {
      Project     = "ClinCase"
      Component   = "infrastructure"
      Environment = var.environment
      ManagedBy   = "terraform"
      CostCenter  = var.cost_center
    }
  }
}

# Secondary region — N. Virginia. Lowest-latency region for US payer
# integrations + best Bedrock model availability for "burst overflow" if
# ap-south-1 hits provisioned-throughput limits.
provider "aws" {
  alias  = "secondary"
  region = var.secondary_region
  default_tags {
    tags = {
      Project     = "ClinCase"
      Component   = "infrastructure"
      Environment = var.environment
      ManagedBy   = "terraform"
      CostCenter  = var.cost_center
    }
  }
}
