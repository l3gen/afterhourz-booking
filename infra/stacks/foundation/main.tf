# FOUNDATION: everything that must survive the nightly teardown of the API stack.
# Cost while idle is pennies: DynamoDB on-demand, S3, CloudFront, one secret, Route 53 records.

data "aws_caller_identity" "current" {}

locals {
  account_id       = data.aws_caller_identity.current.account_id
  ses_identity_arn = "arn:aws:ses:${var.region}:${local.account_id}:identity/${var.domain_zone_name}"
  site_url         = "https://${var.site_hostname}"
}

module "data" {
  source                 = "../../modules/data"
  env                    = var.env
  deletion_protection    = var.deletion_protection
  point_in_time_recovery = var.point_in_time_recovery
}

module "edge" {
  source        = "../../modules/edge"
  env           = var.env
  zone_name     = var.domain_zone_name
  site_hostname = var.site_hostname
}

module "reminders" {
  source             = "../../modules/reminders"
  env                = var.env
  table_name         = module.data.table_name
  table_arn          = module.data.table_arn
  ses_from           = var.ses_from
  ses_identity_arn   = local.ses_identity_arn
  site_url           = local.site_url
  sms_enabled        = var.sms_enabled
  timezone           = var.timezone
  log_retention_days = var.log_retention_days
}

module "cost_guard" {
  source                   = "../../modules/cost_guard"
  env                      = var.env
  region                   = var.region
  alert_email              = var.alert_email
  monthly_budget_usd       = var.monthly_budget_usd
  filter_budget_by_env_tag = var.filter_budget_by_env_tag
  reaper_mode              = var.reaper_mode
  enable_cost_analyst      = var.enable_cost_analyst
  bedrock_model_id         = var.bedrock_model_id
  create_anomaly_monitor   = var.create_anomaly_monitor
  log_retention_days       = var.log_retention_days
}

# Discovery values for CI (it reads these instead of hard-coding names).
resource "aws_ssm_parameter" "web_bucket" {
  name  = "/afterhourz/${var.env}/web_bucket"
  type  = "String"
  value = module.edge.web_bucket
}

resource "aws_ssm_parameter" "distribution_id" {
  name  = "/afterhourz/${var.env}/cloudfront_distribution_id"
  type  = "String"
  value = module.edge.distribution_id
}

resource "aws_ssm_parameter" "site_url" {
  name  = "/afterhourz/${var.env}/site_url"
  type  = "String"
  value = local.site_url
}
