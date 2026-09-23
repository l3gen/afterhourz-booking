# First deploy: problems hit and how they were fixed

A running log of every failure and blocker while taking AfterHourzKutz from repo to a live
dev environment (started 2026-09-23). Each entry: what broke, why, and the fix.

## Account and setup

| # | Symptom | Root cause | Fix |
|---|---------|------------|-----|
| 1 | `git push` → `Repository not found` | The GitHub repo had not been created yet; git does not create it on push. | Created `l3gen/afterhourz-booking` on GitHub, then pushed. |
| 2 | `route53domains check-domain-availability` → `Free Tier accounts are not supported for this service` | The AWS account was on the new **Free plan**, which blocks domain registration (and closes the account when credits run out). | Upgraded the account to the **Paid plan**, then registered `afterhourzkutz.com` in Route 53 ($16/yr). |
| 3 | Domain not showing after "registering" | Checkout was never submitted (`list-operations` was empty). | Submitted the order; watched `list-operations` until `SUCCESSFUL`; Route 53 created the hosted zone automatically. |
| 4 | `gh` not recognized right after `winget install` | The open PowerShell session had the old PATH. | Reopened PowerShell (or reloaded `$env:Path`), then `gh auth login`. |

## Bootstrap (run locally)

| # | Symptom | Root cause | Fix |
|---|---------|------------|-----|
| 5 | `terraform init -migrate-state` → `InvalidBucketName` for `afterhourz-tfstate-<account-id>` | The backend block still had the placeholder bucket name. | Set `bucket = "afterhourz-tfstate-283335735389"` in `infra/bootstrap/versions.tf`, migrated, confirmed `No changes`. |

## CI (GitHub Actions)

| # | Symptom | Root cause | Fix |
|---|---------|------------|-----|
| 6 | `terraform fmt -check` failed | Hand edits left bad indentation in `bootstrap/versions.tf` and a tfvars file. | `terraform fmt -recursive infra`. Added `.gitattributes` (LF endings) to stop CRLF churn from Windows. |
| 7 | tflint: `terraform "required_version" attribute is required` (5 modules) | Child modules had no `required_version`. | Added `required_version = ">= 1.10"` to every `infra/modules/*/versions.tf`. |
| 8 | Trivy: 4 fixable HIGH CVEs (jaraco.context, wheel, …) | All inside setuptools/wheel shipped with the `python:3.11-slim` base image, not in app dependencies. | Runtime image now uninstalls pip/setuptools/wheel (not needed at runtime). |
| 9 | actionlint: SC2034 (`i` unused) and SC2129 (repeated `>> $GITHUB_OUTPUT`) | Shellcheck findings in `ci.yml` and `terraform-stack.yml`. | Loop variable → `_`; grouped the three redirects into one `{ …; } >> "$GITHUB_OUTPUT"`. |
| 10 | Workflow fixes "didn't take" | Files were copied into `.github/` after the commit, so the old versions ran. | Committed them separately. Lesson: check `git status` before pushing. |
| — | Checkov `CKV_AWS_*` annotations (e.g. 109/110 on the deploy policy) | Informational: Checkov runs with `soft_fail: true`. | Tracked as hardening (see below). |

## Deploy (GitHub → AWS)

| # | Symptom | Root cause | Fix |
|---|---------|------------|-----|
| 11 | `configure-aws-credentials`: `Could not assume role with OIDC` | The repo uses GitHub's **immutable OIDC subject claims** (`repo:l3gen@144878904/afterhourz-booking@1383540744:…`), but the IAM trust policies expected `repo:l3gen/afterhourz-booking:…`. Found with `gh api repos/l3gen/afterhourz-booking/actions/oidc/customization/sub`. | Added `github_sub_prefix` to bootstrap and put it in `terraform.tfvars`; re-applied bootstrap (3 trust policies updated). |
| 12 | Foundation apply: `CreationLimitExceededException … one notification can only have 1 subscribers with type of SNS` | The 100%-actual budget alert targeted two SNS topics; AWS Budgets allows one. | That alert now targets only the breach topic; the reaper Lambda it triggers emails the alerts topic. |
| 13 | Foundation apply: `reading ZIP file (…/.build/reaper.zip): no such file` (also cost_analyst, reminders) | Lambda zips were built during **plan** in one CI job; **apply** runs in another job that only received `tfplan`. | Zips now build into `infra/stacks/<stack>/.build/` and are uploaded with the plan artifact (`include-hidden-files: true`). |
| 14 | Foundation plan: `afterhourz-gha-plan is not authorized to perform: secretsmanager:GetSecretValue` | After the partial apply created the app secret, refresh must read its value; `ReadOnlyAccess` doesn't allow that. | Plan role gets `GetSecretValue` on `afterhourz/*` only (it can already read state, which holds the same value). |

## Hardening backlog (not blockers)

- **Permissions boundary for CI-created roles.** The deploy role can manage any `afterhourz-*` role, so a malicious workflow change could create an admin role. Add a boundary that every `afterhourz-*` role must carry. (Checkov CKV_AWS_109/110.)
- **Dependabot PR #1 (Python 3.11 → 3.14):** upgrade Dockerfile, CI, `pyproject.toml`, and Lambda runtimes together in one PR.
- **Node 20 action deprecation warnings:** bump `actions/*` to their Node 24 majors.
- **DMARC reports to iCloud** likely won't arrive (cross-domain authorization); switch to an address on the domain later.
- **Repo is public.** Fine (no secrets), but decide deliberately.
- Request **SES production access** before real customers book.
