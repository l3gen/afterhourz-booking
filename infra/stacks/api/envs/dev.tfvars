env              = "dev"
admin_emails     = "linuxsmart9@gmail.com"                                                    # Google account(s) allowed into /admin
google_client_id = "402642945384-vm98u3e7eva6ou991hl3q8re2h5up6vl.apps.googleusercontent.com" # OAuth Web client ID (docs/SETUP.md, step 5)
# ecr_repository_url and state_bucket are passed by CI from repo variables.

# Cheapest possible shape: one Spot task, no alarms, short logs.
desired_count = 1
use_spot      = true
enable_alarms = false
