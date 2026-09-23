variable "env" {
  type = string
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "region" {
  type    = string
  default = "us-east-1" # keep: CloudFront certificates must live in us-east-1
}

variable "domain_zone_name" {
  type        = string
  description = "Existing Route 53 public zone, e.g. afterhourzkutz.com"
}

variable "site_hostname" {
  type        = string
  description = "Public hostname for this environment, e.g. www.afterhourzkutz.com or dev.afterhourzkutz.com"
}

variable "ses_from" {
  type        = string
  description = "Sender address on the SES-verified domain, e.g. bookings@afterhourzkutz.com"
}

variable "alert_email" {
  type = string
}

variable "monthly_budget_usd" {
  type = number
}

variable "filter_budget_by_env_tag" {
  type    = bool
  default = true
}

variable "reaper_mode" {
  type    = string
  default = "notify"
  validation {
    condition     = contains(["destroy", "notify"], var.reaper_mode)
    error_message = "reaper_mode must be destroy or notify."
  }
}

variable "enable_cost_analyst" {
  type    = bool
  default = true
}

variable "bedrock_model_id" {
  type        = string
  description = "Bedrock model or inference-profile ID for the cost analyst. Verify it is enabled for your account/region."
  default     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "create_anomaly_monitor" {
  type        = bool
  default     = false
  description = "Account-wide Cost Anomaly Detection. Enable in exactly one environment (prod)."
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "point_in_time_recovery" {
  type    = bool
  default = false
}

variable "sms_enabled" {
  type    = bool
  default = false
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "timezone" {
  type    = string
  default = "America/New_York"
}
