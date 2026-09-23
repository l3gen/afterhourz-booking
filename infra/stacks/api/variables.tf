variable "env" {
  type = string
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "state_bucket" {
  type        = string
  description = "Terraform state bucket (to read the foundation stack's outputs)."
}

variable "ecr_repository_url" {
  type        = string
  description = "From bootstrap output ecr_repository_url."
}

variable "image_tag" {
  type        = string
  description = "Git-SHA image tag to run. Set by the pipeline; use any value for `destroy`."
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "use_spot" {
  type    = bool
  default = false
}

variable "enable_deletion_protection" {
  type    = bool
  default = false
}

variable "enable_alarms" {
  type    = bool
  default = false
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "google_client_id" {
  type    = string
  default = ""
}

variable "admin_emails" {
  type        = string
  description = "Comma-separated Google accounts allowed into /admin."
}

variable "sms_enabled" {
  type    = bool
  default = false
}

variable "payments_enabled" {
  type        = bool
  default     = false
  description = "Turn on ONLY after STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET are set in the app secret."
}

variable "google_calendar_id" {
  type    = string
  default = ""
}
