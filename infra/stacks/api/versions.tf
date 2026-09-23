terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }

  backend "s3" {}
}

# Everything created by this stack is tagged Ephemeral=true. The cost reaper finds and
# scales down / deletes resources by these tags, so do not remove them.
provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "afterhourz", Env = var.env, ManagedBy = "terraform", Ephemeral = "true" }
  }
}
