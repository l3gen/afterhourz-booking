# GitHub Actions authenticates to AWS with short-lived OIDC tokens. No access keys exist
# anywhere. Each role's trust policy pins the exact repo AND the GitHub Environment (or PR
# context), so a workflow running from a feature branch physically cannot assume the prod role.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

locals {
  oidc_arn = aws_iam_openid_connect_provider.github.arn
  role_specs = {
    plan = {
      # read-only: PR checks and the plan half of every deploy
      subs = [
        "repo:${var.github_repo}:pull_request",
        "repo:${var.github_repo}:ref:refs/heads/main",
        "repo:${var.github_repo}:ref:refs/tags/v*", # release tags (image verification + prod plan)
      ]
    }
    deploy-dev = {
      subs = ["repo:${var.github_repo}:environment:dev"]
    }
    deploy-prod = {
      subs = ["repo:${var.github_repo}:environment:production"]
    }
  }
}

data "aws_iam_policy_document" "trust" {
  for_each = local.role_specs
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = each.value.subs
    }
  }
}

resource "aws_iam_role" "gha" {
  for_each             = local.role_specs
  name                 = "afterhourz-gha-${each.key}"
  assume_role_policy   = data.aws_iam_policy_document.trust[each.key].json
  max_session_duration = 3600
}

# ---- plan role: read-only, and explicitly unable to read customer data ----------------
resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.gha["plan"].name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

data "aws_iam_policy_document" "plan_extra" {
  statement {
    sid       = "NoCustomerData"
    effect    = "Deny"
    actions   = ["dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:Query", "dynamodb:Scan", "dynamodb:PartiQLSelect", "dynamodb:ExportTableToPointInTime"]
    resources = ["arn:aws:dynamodb:*:${local.account_id}:table/afterhourz-*"]
  }
}

resource "aws_iam_role_policy" "plan_extra" {
  role   = aws_iam_role.gha["plan"].id
  name   = "deny-customer-data"
  policy = data.aws_iam_policy_document.plan_extra.json
}

# ---- deploy roles: service-scoped (NOT AdministratorAccess) ----------------------------
data "aws_iam_policy_document" "deploy" {
  statement {
    sid = "ServicesTerraformManages"
    actions = [
      "ec2:*", "ecs:*", "elasticloadbalancing:*", "logs:*", "dynamodb:*", "s3:*", "cloudfront:*",
      "route53:*", "acm:*", "ses:*", "lambda:*", "scheduler:*", "events:*", "sns:*", "budgets:*",
      "ce:*", "secretsmanager:*", "ecr:*", "tag:*", "cloudwatch:*", "ssm:*", "application-autoscaling:*",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "ManageOnlyProjectRoles"
    actions   = ["iam:*"]
    resources = ["arn:aws:iam::${local.account_id}:role/afterhourz-*", "arn:aws:iam::${local.account_id}:policy/afterhourz-*"]
  }

  statement {
    sid       = "ReadIamAndServiceLinkedRoles"
    actions   = ["iam:Get*", "iam:List*", "iam:CreateServiceLinkedRole"]
    resources = ["*"]
  }

  # Prevent privilege escalation: CI can never edit the CI roles themselves.
  statement {
    sid       = "CannotTouchCiRoles"
    effect    = "Deny"
    actions   = ["iam:*"]
    resources = ["arn:aws:iam::${local.account_id}:role/afterhourz-gha-*"]
  }
}

resource "aws_iam_policy" "deploy" {
  name   = "afterhourz-gha-deploy"
  policy = data.aws_iam_policy_document.deploy.json
}

resource "aws_iam_role_policy_attachment" "deploy" {
  for_each   = toset(["deploy-dev", "deploy-prod"])
  role       = aws_iam_role.gha[each.key].name
  policy_arn = aws_iam_policy.deploy.arn
}
