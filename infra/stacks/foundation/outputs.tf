output "site_url" { value = local.site_url }
output "table_name" { value = module.data.table_name }
output "table_arn" { value = module.data.table_arn }
output "secret_arn" { value = module.data.secret_arn }
output "zone_id" { value = module.edge.zone_id }
output "origin_hostname" { value = module.edge.origin_hostname }
output "certificate_arn" { value = module.edge.certificate_arn }
output "origin_verify_secret" {
  value     = module.edge.origin_verify_secret
  sensitive = true
}
output "web_bucket" { value = module.edge.web_bucket }
output "distribution_id" { value = module.edge.distribution_id }
output "alerts_topic_arn" { value = module.cost_guard.alerts_topic_arn }
output "ses_identity_arn" { value = local.ses_identity_arn }
output "ses_from" { value = var.ses_from }
