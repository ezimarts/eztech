terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
}

provider "aws" {
  region              = var.aws_region
  profile             = "eztech"
  allowed_account_ids = ["939365918012"]
}

# CloudFront ACM certificates must be in us-east-1.
provider "aws" {
  alias               = "use1"
  region              = "us-east-1"
  profile             = "eztech"
  allowed_account_ids = ["939365918012"]
}
