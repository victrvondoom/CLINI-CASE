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

# Multi-region providers — one per probe region
provider "aws" {
  alias   = "us_east_1"
  region  = "us-east-1"
  default_tags { tags = { Project = "ClinCase", Component = "synthetic-monitoring", ProbeRegion = "us-east-1" } }
}

provider "aws" {
  alias   = "us_west_2"
  region  = "us-west-2"
  default_tags { tags = { Project = "ClinCase", Component = "synthetic-monitoring", ProbeRegion = "us-west-2" } }
}

provider "aws" {
  alias   = "eu_west_1"
  region  = "eu-west-1"
  default_tags { tags = { Project = "ClinCase", Component = "synthetic-monitoring", ProbeRegion = "eu-west-1" } }
}

provider "aws" {
  alias   = "ap_northeast_1"
  region  = "ap-northeast-1"
  default_tags { tags = { Project = "ClinCase", Component = "synthetic-monitoring", ProbeRegion = "ap-northeast-1" } }
}
