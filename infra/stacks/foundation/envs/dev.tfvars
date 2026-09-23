env                = "dev"
domain_zone_name   = "example.com"     # <- your Route 53 zone
site_hostname      = "dev.example.com" # <- dev site lives on a subdomain
ses_from           = "bookings@example.com"
alert_email        = "you@example.com"
monthly_budget_usd = 25

# Dev is disposable: the reaper is allowed to tear it down when the budget trips.
reaper_mode         = "destroy"
enable_cost_analyst = true
