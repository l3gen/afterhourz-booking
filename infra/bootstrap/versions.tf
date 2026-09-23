terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # After the first apply, migrate this state into the bucket it created:
  #   1) uncomment the backend block  2) terraform init -migrate-state
  backend "s3" {
    bucket       = "afterhourz-tfstate-283335735389"
    key          = "bootstrap/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "afterhourz", Env = "shared", ManagedBy = "terraform", Ephemeral = "false" }
  }
}

data "aws_caller_identity" "current" {}
