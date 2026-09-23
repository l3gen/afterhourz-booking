terraform {
  required_version = ">= 1.10"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    random  = { source = "hashicorp/random", version = "~> 3.6" }
    archive = { source = "hashicorp/archive", version = "~> 2.7" }
  }

  # Bucket comes from `-backend-config="bucket=..."`; the rest from envs/<env>.backend.hcl.
  backend "s3" {}
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "afterhourz", Env = var.env, ManagedBy = "terraform", Ephemeral = "false" }
  }
}
