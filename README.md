# AfterHourzKutz booking site

Online appointment booking for a barbershop: clients pick a service and time, sign in with Google, pay a deposit, and get confirmations and reminders. The owner gets an admin dashboard, Google Calendar sync, and analytics on which bookings came from Google.

**Stack:** React (Vite) · Python FastAPI · DynamoDB · AWS (CloudFront + S3, ECS Fargate, Lambda) · Terraform · GitHub Actions

```
backend/     FastAPI API + Dockerfile + tests
frontend/    React site (slideshow background, booking flow, admin)
lambdas/     reminders, cost reaper, AI cost analyst
infra/       Terraform: bootstrap/ (one-time), stacks/foundation (always on), stacks/api (destroyed nightly in dev)
.github/     CI/CD workflows with approval gates
docs/        ARCHITECTURE.md · SETUP.md · CICD.md
```

## Try it locally in two minutes

```bash
make setup
make db     # terminal 1
make api    # terminal 2
make web    # terminal 3  ->  http://localhost:5173
```

## Read next

1. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the design, why it is containerized (the API, not the site), the nightly-destroy cost strategy, and the Bedrock cost analyst.
2. [docs/SETUP.md](docs/SETUP.md): step by step from zero to live (AWS, GitHub, Google, Stripe).
3. [docs/CICD.md](docs/CICD.md): the pipeline, approval gates, and GitHub settings.

## Before you launch

- [ ] Replace the placeholder photos in `frontend/public/gallery/` and list them in `frontend/src/gallery.js`
- [ ] Edit business details in `frontend/src/siteConfig.js` and the JSON-LD block in `frontend/index.html`
- [ ] Edit services and prices in `backend/app/catalog.py`
- [ ] Set your domain in the `infra/**/envs/*.tfvars` files and `.github/CODEOWNERS`
- [ ] Run `terraform init` in each root module and commit the `.terraform.lock.hcl` files
- [ ] Deploy to dev and test every flow (booking, cancel, deposit, admin) before production
