env              = "prod"
admin_emails     = "you@gmail.com"
google_client_id = ""
vpc_cidr         = "10.30.0.0/16"

# Two on-demand tasks in two AZs; a rolling deploy never drops below 2 healthy.
desired_count              = 2
use_spot                   = false
enable_alarms              = true
enable_deletion_protection = true
log_retention_days         = 30

# Flip to true only after the Stripe keys are in Secrets Manager (docs/SETUP.md, step 7).
payments_enabled = false
