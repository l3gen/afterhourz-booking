# Daily reminder emails/texts. Runs in the always-on foundation stack so reminders keep
# working even while the dev API stack is destroyed overnight.

variable "env" { type = string }
variable "table_name" { type = string }
variable "table_arn" { type = string }
variable "ses_from" { type = string }
variable "ses_identity_arn" { type = string }
variable "site_url" { type = string }
variable "sms_enabled" { type = bool }
variable "timezone" { type = string }
variable "log_retention_days" { type = number }

data "archive_file" "zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambdas/reminders"
  output_path = "${path.module}/.build/reminders.zip"
}

resource "aws_cloudwatch_log_group" "fn" {
  name              = "/aws/lambda/afterhourz-${var.env}-reminders"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "fn" {
  name               = "afterhourz-${var.env}-reminders"
  assume_role_policy = data.aws_iam_policy_document.trust.json
}

data "aws_iam_policy_document" "fn" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.fn.arn}:*"]
  }
  statement {
    actions   = ["dynamodb:Query", "dynamodb:UpdateItem"]
    resources = [var.table_arn, "${var.table_arn}/index/*"]
  }
  statement {
    actions   = ["ses:SendEmail"]
    resources = [var.ses_identity_arn]
    condition {
      test     = "StringEquals"
      variable = "ses:FromAddress"
      values   = [var.ses_from]
    }
  }
  dynamic "statement" {
    for_each = var.sms_enabled ? [1] : []
    content {
      actions   = ["sns:Publish"]
      resources = ["*"]
    }
  }
}

resource "aws_iam_role_policy" "fn" {
  role   = aws_iam_role.fn.id
  name   = "reminders"
  policy = data.aws_iam_policy_document.fn.json
}

resource "aws_lambda_function" "fn" {
  function_name    = "afterhourz-${var.env}-reminders"
  role             = aws_iam_role.fn.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.zip.output_path
  source_code_hash = data.archive_file.zip.output_base64sha256
  timeout          = 60
  memory_size      = 128

  environment {
    variables = {
      TABLE_NAME      = var.table_name
      TIMEZONE        = var.timezone
      SES_FROM        = var.ses_from
      SMS_ENABLED     = tostring(var.sms_enabled)
      FRONTEND_ORIGIN = var.site_url
    }
  }

  depends_on = [aws_cloudwatch_log_group.fn]
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

resource "aws_iam_role" "scheduler" {
  name               = "afterhourz-${var.env}-reminders-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

resource "aws_iam_role_policy" "scheduler" {
  role = aws_iam_role.scheduler.id
  name = "invoke"
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "lambda:InvokeFunction", Resource = aws_lambda_function.fn.arn }]
  })
}

# 4pm shop time every day: tomorrow's clients get a nudge.
resource "aws_scheduler_schedule" "daily" {
  name                         = "afterhourz-${var.env}-reminders"
  schedule_expression          = "cron(0 16 * * ? *)"
  schedule_expression_timezone = var.timezone

  flexible_time_window {
    mode = "OFF"
  }
  target {
    arn      = aws_lambda_function.fn.arn
    role_arn = aws_iam_role.scheduler.arn
  }
}
