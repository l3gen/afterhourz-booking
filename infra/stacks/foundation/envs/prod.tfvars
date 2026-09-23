env                = "prod"
domain_zone_name   = "afterhourzkutz.com"     # <- your Route 53 zone
site_hostname      = "www.afterhourzkutz.com" # <- or the apex, e.g. "afterhourzkutz.com"
ses_from           = "bookings@afterhourzkutz.com"
alert_email        = "dwilliam700@icloud.com"
monthly_budget_usd = 75

# Prod is never taken down automatically: the reaper only reports.
reaper_mode            = "notify"
enable_cost_analyst    = true
create_anomaly_monitor = true # account-wide, enable in ONE environment only
deletion_protection    = true
point_in_time_recovery = true # 35-day restore for client data
log_retention_days     = 30
