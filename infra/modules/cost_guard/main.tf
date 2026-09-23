# Cost control in three independent layers. See docs/ARCHITECTURE.md for the reasoning.
#
#  1. PREVENT   Nightly `terraform destroy` of the dev API stack (GitHub Actions) + this
#               module's scheduled reaper as a safety net if that job ever fails.
#  2. LIMIT     AWS Budgets. At 100% of the monthly budget the deterministic reaper Lambda
#               scales dev services to zero and deletes the dev ALB. In prod it only alerts.
#  3. EXPLAIN   A daily Lambda asks Amazon Bedrock to analyse Cost Explorer data and emails
#               the findings. Advisory only: it has NO destructive permissions.

variable "env" { type = string }
variable "region" { type = string }
variable "alert_email" { type = string }
variable "monthly_budget_usd" { type = number }
variable "filter_budget_by_env_tag" { type = bool }
variable "reaper_mode" { type = string } # destroy | notify
variable "enable_cost_analyst" { type = bool }
variable "bedrock_model_id" { type = string }
variable "create_anomaly_monitor" { type = bool }
variable "log_retention_days" { type = number }

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  prefix     = "afterhourz-${var.env}"
}

# ------------------------------------------------------------------ topics
resource "aws_sns_topic" "alerts" {
  name = "${local.prefix}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email # you must click the confirmation link AWS emails you
}

# Only Budgets publishes here, and only the reaper listens: this is the "spend limit hit" wire.
resource "aws_sns_topic" "breach" {
  name = "${local.prefix}-budget-breach"
}

data "aws_iam_policy_document" "topics" {
  statement {
    sid       = "BudgetsAndCostAnomalyMayPublishAlerts"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com", "costalerts.amazonaws.com", "cloudwatch.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "breach_topic" {
  statement {
    sid       = "BudgetsMayPublishBreach"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.breach.arn]
    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com"]
    }
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.topics.json
}

resource "aws_sns_topic_policy" "breach" {
  arn    = aws_sns_topic.breach.arn
  policy = data.aws_iam_policy_document.breach_topic.json
}

# ------------------------------------------------------------------ budget
resource "aws_budgets_budget" "monthly" {
  name         = "${local.prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Needs the `Env` cost-allocation tag activated once in the Billing console (see docs/SETUP.md).
  dynamic "cost_filter" {
    for_each = var.filter_budget_by_env_tag ? [1] : []
    content {
      name   = "TagKeyValue"
      values = [format("user:Env$%s", var.env)]
    }
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 50
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.alerts.arn]
  }
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.alerts.arn]
  }
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_sns_topic_arns = [aws_sns_topic.alerts.arn]
  }
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.alerts.arn, aws_sns_topic.breach.arn]
  }
}

resource "aws_ce_anomaly_monitor" "services" {
  count             = var.create_anomaly_monitor ? 1 : 0
  name              = "afterhourz-services"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
}

resource "aws_ce_anomaly_subscription" "alerts" {
  count            = var.create_anomaly_monitor ? 1 : 0
  name             = "afterhourz-anomalies"
  frequency        = "IMMEDIATE"
  monitor_arn_list = [aws_ce_anomaly_monitor.services[0].arn]

  subscriber {
    type    = "SNS"
    address = aws_sns_topic.alerts.arn
  }
  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      match_options = ["GREATER_THAN_OR_EQUAL"]
      values        = ["5"]
    }
  }
}

# ------------------------------------------------------------------ shared lambda plumbing
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

# ------------------------------------------------------------------ reaper (deterministic)
data "archive_file" "reaper" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambdas/reaper"
  output_path = "${path.module}/.build/reaper.zip"
}

resource "aws_cloudwatch_log_group" "reaper" {
  name              = "/aws/lambda/${local.prefix}-cost-reaper"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "reaper" {
  name               = "${local.prefix}-cost-reaper"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "reaper" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.reaper.arn}:*"]
  }
  statement {
    sid       = "FindTaggedResources"
    actions   = ["tag:GetResources"]
    resources = ["*"]
  }
  # Blast radius is limited to THIS environment's ECS services and load balancers, by name.
  statement {
    sid       = "ScaleDownServices"
    actions   = ["ecs:UpdateService"]
    resources = ["arn:aws:ecs:${var.region}:${local.account_id}:service/${local.prefix}/*"]
  }
  statement {
    sid       = "DeleteLoadBalancer"
    actions   = ["elasticloadbalancing:DeleteLoadBalancer"]
    resources = ["arn:aws:elasticloadbalancing:${var.region}:${local.account_id}:loadbalancer/app/${local.prefix}/*"]
  }
  statement {
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }
}

resource "aws_iam_role_policy" "reaper" {
  role   = aws_iam_role.reaper.id
  name   = "reaper"
  policy = data.aws_iam_policy_document.reaper.json
}

resource "aws_lambda_function" "reaper" {
  function_name    = "${local.prefix}-cost-reaper"
  role             = aws_iam_role.reaper.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.reaper.output_path
  source_code_hash = data.archive_file.reaper.output_base64sha256
  timeout          = 60
  memory_size      = 128

  environment {
    variables = {
      ENVIRONMENT     = var.env
      REAPER_MODE     = var.reaper_mode
      ALERT_TOPIC_ARN = aws_sns_topic.alerts.arn
    }
  }
  depends_on = [aws_cloudwatch_log_group.reaper]
}

resource "aws_lambda_permission" "breach" {
  statement_id  = "AllowBreachTopic"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reaper.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.breach.arn
}

resource "aws_sns_topic_subscription" "reaper" {
  topic_arn = aws_sns_topic.breach.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.reaper.arn
}

# Safety net: even if the GitHub nightly-destroy job fails (or GitHub disables the schedule
# after 60 idle days), dev gets swept at 4am. Dev only, never prod.
resource "aws_iam_role" "reaper_scheduler" {
  count              = var.reaper_mode == "destroy" ? 1 : 0
  name               = "${local.prefix}-reaper-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

resource "aws_iam_role_policy" "reaper_scheduler" {
  count = var.reaper_mode == "destroy" ? 1 : 0
  role  = aws_iam_role.reaper_scheduler[0].id
  name  = "invoke"
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "lambda:InvokeFunction", Resource = aws_lambda_function.reaper.arn }]
  })
}

resource "aws_scheduler_schedule" "reaper_sweep" {
  count                        = var.reaper_mode == "destroy" ? 1 : 0
  name                         = "${local.prefix}-reaper-nightly-sweep"
  schedule_expression          = "cron(0 4 * * ? *)"
  schedule_expression_timezone = "America/New_York"

  flexible_time_window {
    mode = "OFF"
  }
  target {
    arn      = aws_lambda_function.reaper.arn
    role_arn = aws_iam_role.reaper_scheduler[0].arn
  }
}

# ------------------------------------------------------------------ AI cost analyst (advisory)
data "archive_file" "analyst" {
  count       = var.enable_cost_analyst ? 1 : 0
  type        = "zip"
  source_dir  = "${path.module}/../../../lambdas/cost_analyst"
  output_path = "${path.module}/.build/cost_analyst.zip"
}

resource "aws_cloudwatch_log_group" "analyst" {
  count             = var.enable_cost_analyst ? 1 : 0
  name              = "/aws/lambda/${local.prefix}-cost-analyst"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "analyst" {
  count              = var.enable_cost_analyst ? 1 : 0
  name               = "${local.prefix}-cost-analyst"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "analyst" {
  count = var.enable_cost_analyst ? 1 : 0
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.analyst[0].arn}:*"]
  }
  statement {
    sid       = "ReadCosts"
    actions   = ["ce:GetCostAndUsage"]
    resources = ["*"]
  }
  # Inference profiles route to foundation models in several regions, so both ARNs are needed.
  statement {
    sid     = "InvokeClaudeOnBedrock"
    actions = ["bedrock:InvokeModel"]
    resources = [
      "arn:aws:bedrock:*::foundation-model/anthropic.*",
      "arn:aws:bedrock:*:${local.account_id}:inference-profile/*anthropic.*",
    ]
  }
  statement {
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }
}

resource "aws_iam_role_policy" "analyst" {
  count  = var.enable_cost_analyst ? 1 : 0
  role   = aws_iam_role.analyst[0].id
  name   = "analyst"
  policy = data.aws_iam_policy_document.analyst[0].json
}

resource "aws_lambda_function" "analyst" {
  count            = var.enable_cost_analyst ? 1 : 0
  function_name    = "${local.prefix}-cost-analyst"
  role             = aws_iam_role.analyst[0].arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.analyst[0].output_path
  source_code_hash = data.archive_file.analyst[0].output_base64sha256
  timeout          = 90
  memory_size      = 256

  environment {
    variables = {
      ENVIRONMENT        = var.env
      BEDROCK_MODEL_ID   = var.bedrock_model_id
      ALERT_TOPIC_ARN    = aws_sns_topic.alerts.arn
      MONTHLY_BUDGET_USD = tostring(var.monthly_budget_usd)
    }
  }
  depends_on = [aws_cloudwatch_log_group.analyst]
}

resource "aws_iam_role" "analyst_scheduler" {
  count              = var.enable_cost_analyst ? 1 : 0
  name               = "${local.prefix}-analyst-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

resource "aws_iam_role_policy" "analyst_scheduler" {
  count = var.enable_cost_analyst ? 1 : 0
  role  = aws_iam_role.analyst_scheduler[0].id
  name  = "invoke"
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "lambda:InvokeFunction", Resource = aws_lambda_function.analyst[0].arn }]
  })
}

resource "aws_scheduler_schedule" "analyst_daily" {
  count                        = var.enable_cost_analyst ? 1 : 0
  name                         = "${local.prefix}-cost-analyst-daily"
  schedule_expression          = "cron(0 7 * * ? *)"
  schedule_expression_timezone = "America/New_York"

  flexible_time_window {
    mode = "OFF"
  }
  target {
    arn      = aws_lambda_function.analyst[0].arn
    role_arn = aws_iam_role.analyst_scheduler[0].arn
  }
}

output "alerts_topic_arn" { value = aws_sns_topic.alerts.arn }
