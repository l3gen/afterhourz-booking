env              = "prod"
admin_emails     = "linuxsmart9@gmail.com"
google_client_id = "402642945384-vm98u3e7eva6ou991hl3q8re2h5up6vl.apps.googleusercontent.com"
vpc_cidr         = "10.30.0.0/16"

# Two on-demand tasks in two AZs; a rolling deploy never drops below 2 healthy.
desired_count              = 2
use_spot                   = false
enable_alarms              = true
enable_deletion_protection = true
log_retention_days         = 30

# Flip to true only after the Stripe keys are in Secrets Manager (docs/SETUP.md, step 7).
payments_enabled = false
