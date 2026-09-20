# =============================================================================
# ClinCase — Bedrock VPC Endpoint + IAM Terraform
# =============================================================================
#
# Realizes the AWS-published architectural guidance for governed Bedrock
# access (https://aws.amazon.com/blogs/architecture/category/artificial-
# intelligence/amazon-machine-learning/amazon-bedrock/): VPC endpoints +
# endpoint policies + per-model-id IAM conditions, with PrivateLink as the
# only network path the application can take to Bedrock.

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
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "ClinCase"
      Component   = "bedrock-governance"
      Environment = var.environment
      ManagedBy   = "terraform"
      CostCenter  = var.cost_center
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_eks_cluster" "this" {
  name = var.eks_cluster_name
}

locals {
  oidc_provider = replace(data.aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")
}
