output "state_bucket" {
  value = aws_s3_bucket.tfstate.bucket
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "account_id" {
  value = local.account_id
}

output "github_role_arns" {
  value = { for k, r in aws_iam_role.gha : k => r.arn }
}

output "next_steps" {
  value = <<-EOT
    1. In GitHub: Settings > Secrets and variables > Actions > Variables, add:
         AWS_ACCOUNT_ID = ${local.account_id}
         AWS_REGION     = ${var.region}
         TF_STATE_BUCKET = ${aws_s3_bucket.tfstate.bucket}
    2. Create GitHub Environments 'dev' and 'production' (production: required reviewers, main only).
    3. Ask AWS to move SES out of the sandbox (console: SES > Account dashboard > Request production access).
  EOT
}
