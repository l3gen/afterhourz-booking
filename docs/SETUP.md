# Setup: from zero to live

Work through this in order. Do everything in **dev** first; production is the same steps once dev works.

## 0. What you need

- An AWS account (turn on MFA for the root user, and use an admin IAM/SSO user for the one-time bootstrap, never root).
- A domain whose DNS is hosted in **Route 53** (register it there, or create a public hosted zone and point your registrar's nameservers at it). Pick hostnames, e.g. `www.yourdomain.com` (prod) and `dev.yourdomain.com` (dev).
- A GitHub repository for this code.
- Locally: Terraform 1.10+ (1.13 is what CI uses), AWS CLI, Python 3.11, Node 22.

## 1. Run it on your laptop (no AWS needed)

```bash
make setup
make db      # terminal 1: local DynamoDB stand-in
make api     # terminal 2: API on :8000
make web     # terminal 3: site on :5173
```

Open http://localhost:5173. Sign-in shows a "Dev sign in" box locally. To see the admin dashboard, sign in as `owner@example.com` at `/admin` (change with `ADMIN_EMAILS=you@gmail.com make api`). Run `make test` and `make lint` any time.

**Add your photos:** put them in `frontend/public/gallery/` (1600px wide, JPG or WebP, under about 250 KB each) and list them in `frontend/src/gallery.js`. They drive both the background slideshow and the gallery grid.

**Make it yours** before launch:
- `frontend/src/siteConfig.js`: phone, address, tagline.
- `frontend/index.html`: the `LocalBusiness` JSON-LD block (name, address, hours, phone), title and description. The `example.com` placeholders are rewritten to your real domain at deploy time.
- `backend/app/catalog.py`: services, prices, durations, deposits.
- Default hours are Tue-Sat 10-7; you edit them any time in the admin dashboard.

## 2. Bootstrap AWS (once, from your laptop)

```bash
cd infra/bootstrap
terraform init
terraform apply \
  -var github_repo=YOUR-USER/YOUR-REPO \
  -var domain_zone_name=yourdomain.com \
  -var dmarc_report_email=you@yourdomain.com
```

This creates the Terraform state bucket, the shared container registry, the GitHub-to-AWS trust roles, and the SES email identity with DKIM. Copy the printed `next_steps`. Then move the bootstrap state into its own bucket (uncomment the `backend` block in `versions.tf`, run `terraform init -migrate-state`).

In the SES console, **request production access** (new accounts can only email verified addresses until you do).

## 3. Configure GitHub

Follow "One-time GitHub settings" in [CICD.md](CICD.md): repository variables, the `dev` and `production` environments (production with you as required reviewer), branch protection, and editing `.github/CODEOWNERS`.

## 4. Edit the Terraform variables

- `infra/stacks/foundation/envs/dev.tfvars` and `prod.tfvars`: your zone, hostname, sender address (`bookings@yourdomain.com`), alert email, monthly budgets.
- `infra/stacks/api/envs/dev.tfvars` and `prod.tfvars`: `admin_emails` (the Google account(s) that may open `/admin`).
- Generate provider lock files and commit them:

```bash
for d in bootstrap stacks/foundation stacks/api; do (cd infra/$d && terraform init -backend=false); done
git add infra/**/.terraform.lock.hcl
```

Then `terraform validate` in each (CI does this too). If validate reports anything, fix it in dev before going further.

## 5. Google: sign-in, calendar, analytics, search

**Sign in with Google (required to book):**
1. console.cloud.google.com > create a project > APIs & Services > OAuth consent screen (External; add your email).
2. Credentials > Create credentials > OAuth client ID > **Web application**. Authorized JavaScript origins: `https://dev.yourdomain.com`, `https://www.yourdomain.com`, `http://localhost:5173`. (No redirect URI is needed for the button flow.)
3. Put the client ID in `infra/stacks/api/envs/*.tfvars` as `google_client_id`. It is public by design.
4. Publish the consent screen ("In production") before real clients use it, or only test users can sign in.

**Google Calendar sync (optional):** enable the Google Calendar API, create a service account, download its JSON key, and share your calendar with the service account's email ("Make changes to events"). Set `google_calendar_id` (your calendar's ID, usually your Gmail address) in the api tfvars, and store the JSON key in the app secret (step 8).

**Search Console:** add your domain property, pick "HTML tag" verification, and put the `content` value in the GitHub variable `VITE_GSC_VERIFICATION`. After the first prod deploy, submit `https://www.yourdomain.com/sitemap.xml`.

**Analytics:** create a GA4 property and put its `G-XXXX` ID in the GitHub variable `VITE_GA_ID` (set it on the `production` environment so dev traffic does not pollute your numbers). The site records `generate_lead`, `begin_checkout`, and `booking_confirmed` events, and each booking stores where it came from.

**Google Business Profile ("Book" button):** claim your listing at business.google.com. Set **Website** to `https://www.yourdomain.com` and the **Appointment link** to:

```
https://www.yourdomain.com/book?utm_source=google&utm_medium=organic&utm_campaign=business-profile
```

Bookings that arrive through that link are labeled `google-organic-business-profile` in your admin dashboard, so you can see how many clients Google actually sends you. The Business Profile listing, reviews, photos, and posting regularly matter more for local rankings than anything on the website; treat the site as the place the "Book" button lands.

## 6. First deploy to dev

Push to `main` (or run **Deploy dev** from the Actions tab). It runs CI, builds the image, and applies the foundation then API stacks, publishes the site, and smoke-tests it. Open `https://dev.yourdomain.com`.

Two follow-ups:
- **Confirm the alert subscription:** AWS emails you a link. Until you click it, no cost alerts reach you.
- **Activate cost-allocation tags:** Billing console > Cost allocation tags > activate `Env` and `Project`. Tags only appear there after the first deploy, and take up to 24 hours to start filtering budgets. Until then the per-environment budget may read $0.

## 7. Stripe deposits (optional, do after step 6 works)

1. Stripe dashboard in **test mode**: copy the secret key (`sk_test_...`).
2. Developers > Webhooks > add endpoint `https://dev.yourdomain.com/api/webhooks/stripe`, events `checkout.session.completed` and `checkout.session.expired`. Copy the signing secret (`whsec_...`).
3. Store both in Secrets Manager (see step 8), then set `payments_enabled = true` in `infra/stacks/api/envs/dev.tfvars` via a pull request.

Test with Stripe's test card `4242 4242 4242 4242`. Repeat with live keys for prod. Stripe retries webhooks for days, so a deposit paid while the dev API was down is still processed when it comes back.

## 8. Put real secrets in place

Terraform creates the secret with a random signing key and blank integrations, and never overwrites your edits:

```bash
aws secretsmanager get-secret-value --secret-id afterhourz/dev/app --query SecretString --output text \
 | jq --arg sk "sk_test_..." --arg wh "whsec_..." --rawfile sa service-account.json \
      '.STRIPE_SECRET_KEY=$sk | .STRIPE_WEBHOOK_SECRET=$wh | .GOOGLE_SERVICE_ACCOUNT_JSON=$sa' > /tmp/secret.json
aws secretsmanager put-secret-value --secret-id afterhourz/dev/app --secret-string file:///tmp/secret.json
rm /tmp/secret.json
```

Containers read secrets when they start, so after changing them force a new deployment: merge any change, or `aws ecs update-service --cluster afterhourz-dev --service api --force-new-deployment`.

## 9. Turn on the cost analyst (Bedrock)

In the AWS console, open Amazon Bedrock and make sure the model in `bedrock_model_id` (default: Claude Haiku 4.5 through the `us.` inference profile) is available to your account and region. Anthropic models may ask you to submit a short use-case form the first time. If you would rather not use it, set `enable_cost_analyst = false`. Model names change over time, so verify the ID in the Bedrock console if the daily email says "AI analysis unavailable".

## 10. Go to production

1. Run **Infra (prod foundation)** from the Actions tab and approve it.
2. Merge to `main`, wait for dev to go green, then tag a release: `git tag v1.0.0 && git push origin v1.0.0`.
3. **Release to production** plans, waits for your approval, then deploys.
4. Repeat steps 5, 7, and 8 for prod (live Stripe keys, prod webhook URL, `https://www.yourdomain.com` as an authorized Google origin, `payments_enabled = true` in `prod.tfvars`).
5. In CloudFront's console (or via a quick DevTools check) confirm no Content-Security-Policy violations are reported, then switch the header in `modules/edge/main.tf` from `Content-Security-Policy-Report-Only` to `Content-Security-Policy`.

## Daily rhythm in dev

- **Merge to main:** dev comes up (or updates) automatically.
- **03:00 UTC (11pm Eastern):** the API stack is destroyed. Data and the static site remain.
- **Morning:** run **Dev up**, or just merge something.
- If anything slips, the AWS-side reaper sweeps dev at 4am Eastern, and the budget trips at 100%.

## Troubleshooting

- **Task will not start, "unable to retrieve secret":** the app secret is missing one of the four keys (`JWT_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `GOOGLE_SERVICE_ACCOUNT_JSON`). Keep all four, even if blank.
- **Container crash-loops on start:** check CloudWatch logs `/ecs/afterhourz-<env>-api`. `PAYMENTS_ENABLED=true` without Stripe keys, or a short `JWT_SECRET`, deliberately stops the app from booting.
- **`/api/*` returns 502:** the API stack is down (normal in dev overnight) or the origin DNS record has not propagated yet.
- **Google button missing:** the site's origin is not in the OAuth client's authorized JavaScript origins, or `google_client_id` is empty.
