terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
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
      Component   = "edge-waf"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
