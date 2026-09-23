env              = "dev"
admin_emails     = "you@gmail.com" # Google account(s) allowed into /admin
google_client_id = ""              # OAuth Web client ID (docs/SETUP.md, step 5)
# ecr_repository_url and state_bucket are passed by CI from repo variables.

# Cheapest possible shape: one Spot task, no alarms, short logs.
desired_count = 1
use_spot      = true
enable_alarms = false
