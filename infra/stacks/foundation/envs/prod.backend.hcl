# bucket is supplied at init time:  terraform init -backend-config=envs/prod.backend.hcl -backend-config="bucket=<state bucket>"
key          = "prod/foundation.tfstate"
region       = "us-east-1"
encrypt      = true
use_lockfile = true
