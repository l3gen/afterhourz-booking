variable "env" { type = string }
variable "deletion_protection" { type = bool }
variable "point_in_time_recovery" { type = bool }

# Single-table design; the key schema must match backend/app/schema.py.
resource "aws_dynamodb_table" "main" {
  name                        = "afterhourz-${var.env}"
  billing_mode                = "PAY_PER_REQUEST" # nothing to pay while idle
  hash_key                    = "pk"
  range_key                   = "sk"
  deletion_protection_enabled = var.deletion_protection

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "gsi1pk"
    type = "S"
  }
  attribute {
    name = "gsi1sk"
    type = "S"
  }
  attribute {
    name = "gsi2pk"
    type = "S"
  }
  attribute {
    name = "gsi2sk"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi1"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "gsi2"
    hash_key        = "gsi2pk"
    range_key       = "gsi2sk"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = var.point_in_time_recovery
  }
  server_side_encryption {
    enabled = true
  }
}

# One JSON secret holds every sensitive setting; ECS injects individual keys as env vars.
# Terraform seeds it once (random JWT key, blank integrations) and then NEVER overwrites it:
# you set the real Stripe / Google values with `aws secretsmanager put-secret-value`.
resource "random_password" "jwt" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "afterhourz/${var.env}/app"
  description             = "AfterHourzKutz ${var.env} application secrets (JSON)"
  recovery_window_in_days = var.env == "prod" ? 7 : 0
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    JWT_SECRET                  = random_password.jwt.result
    STRIPE_SECRET_KEY           = ""
    STRIPE_WEBHOOK_SECRET       = ""
    GOOGLE_SERVICE_ACCOUNT_JSON = ""
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

output "table_name" { value = aws_dynamodb_table.main.name }
output "table_arn" { value = aws_dynamodb_table.main.arn }
output "secret_arn" { value = aws_secretsmanager_secret.app.arn }
