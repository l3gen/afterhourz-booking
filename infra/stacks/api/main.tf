# API STACK (ephemeral): VPC, ALB, ECS Fargate. This is where the money is spent, so in dev it
# is destroyed every night and re-created on demand. Nothing here holds state: data lives in
# DynamoDB and the static site lives in S3/CloudFront, both in the foundation stack.

data "terraform_remote_state" "foundation" {
  backend = "s3"
  config = {
    bucket = var.state_bucket
    key    = "${var.env}/foundation.tfstate"
    region = var.region
  }
}

locals {
  f = data.terraform_remote_state.foundation.outputs
}

module "api" {
  source = "../../modules/api"

  env                        = var.env
  region                     = var.region
  image                      = "${var.ecr_repository_url}:${var.image_tag}"
  desired_count              = var.desired_count
  cpu                        = var.cpu
  memory                     = var.memory
  use_spot                   = var.use_spot
  enable_deletion_protection = var.enable_deletion_protection
  enable_alarms              = var.enable_alarms
  log_retention_days         = var.log_retention_days
  vpc_cidr                   = var.vpc_cidr

  zone_id              = local.f.zone_id
  origin_hostname      = local.f.origin_hostname
  certificate_arn      = local.f.certificate_arn
  origin_verify_secret = local.f.origin_verify_secret
  table_name           = local.f.table_name
  table_arn            = local.f.table_arn
  secret_arn           = local.f.secret_arn
  alerts_topic_arn     = local.f.alerts_topic_arn

  site_url           = local.f.site_url
  google_client_id   = var.google_client_id
  admin_emails       = var.admin_emails
  ses_from           = local.f.ses_from
  ses_identity_arn   = local.f.ses_identity_arn
  sms_enabled        = var.sms_enabled
  payments_enabled   = var.payments_enabled
  google_calendar_id = var.google_calendar_id
}
