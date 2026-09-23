data "aws_iam_policy_document" "ecs_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Execution role: what ECS itself needs to start the task (pull image, write logs, read secret).
resource "aws_iam_role" "execution" {
  name               = "afterhourz-${var.env}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust.json
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secret" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.secret_arn]
  }
}

resource "aws_iam_role_policy" "execution_secret" {
  role   = aws_iam_role.execution.id
  name   = "read-app-secret"
  policy = data.aws_iam_policy_document.execution_secret.json
}

# Task role: what the running application may do. Scoped to this env's table and sender.
resource "aws_iam_role" "task" {
  name               = "afterhourz-${var.env}-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust.json
}

data "aws_iam_policy_document" "task" {
  statement {
    sid = "Table"
    actions = [
      "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem",
      "dynamodb:Query", "dynamodb:ConditionCheckItem",
    ]
    resources = [var.table_arn, "${var.table_arn}/index/*"]
  }
  statement {
    sid       = "SendEmailFromOurAddressOnly"
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
      sid       = "DirectSms"
      actions   = ["sns:Publish"]
      resources = ["*"] # SNS direct-to-phone publishing has no resource ARN
    }
  }
}

resource "aws_iam_role_policy" "task" {
  role   = aws_iam_role.task.id
  name   = "app"
  policy = data.aws_iam_policy_document.task.json
}
