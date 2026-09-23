variable "env" { type = string }
variable "region" { type = string }
variable "image" {
  type        = string
  description = "Full image URI including tag, e.g. 123.dkr.ecr.us-east-1.amazonaws.com/afterhourz-api:abc123"
}
variable "desired_count" { type = number }
variable "cpu" { type = number }
variable "memory" { type = number }
variable "use_spot" { type = bool }
variable "enable_deletion_protection" { type = bool }
variable "enable_alarms" { type = bool }
variable "log_retention_days" { type = number }
variable "vpc_cidr" { type = string }

# wiring from the foundation stack
variable "zone_id" { type = string }
variable "origin_hostname" { type = string }
variable "certificate_arn" { type = string }
variable "origin_verify_secret" {
  type      = string
  sensitive = true
}
variable "table_name" { type = string }
variable "table_arn" { type = string }
variable "secret_arn" { type = string }
variable "alerts_topic_arn" { type = string }

# app configuration
variable "site_url" { type = string }
variable "google_client_id" { type = string }
variable "admin_emails" { type = string }
variable "ses_from" { type = string }
variable "ses_identity_arn" { type = string }
variable "sms_enabled" { type = bool }
variable "payments_enabled" { type = bool }
variable "google_calendar_id" { type = string }
