variable "region" {
  type    = string
  default = "us-east-1"
}

variable "github_repo" {
  type        = string
  description = "GitHub repository allowed to assume the CI roles, as OWNER/REPO."
}

variable "domain_zone_name" {
  type        = string
  description = "Route 53 public hosted zone that already exists, e.g. afterhourzkutz.com"
}

variable "dmarc_report_email" {
  type        = string
  description = "Where DMARC aggregate reports go."
}

variable "github_sub_prefix" {
  type        = string
  default     = ""
  description = "OIDC sub claim prefix when GitHub issues immutable subjects, e.g. repo:OWNER@123/REPO@456. Empty = repo:OWNER/REPO."
}
