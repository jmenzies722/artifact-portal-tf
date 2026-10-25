# artifact-portal-tf

A serverless artifact distribution portal on AWS, built with Terraform: CloudFront, API Gateway, Cognito, Lambda, S3 and DynamoDB, with OIDC CI/CD, SLOs wired to PagerDuty, and zero-downtime secret rotation.

Personal lab project, written from scratch.

## CDN (`modules/cdn`)

One CloudFront distribution serves both the site and the API from the same origin:

| Path      | Origin                                  | Caching            |
|-----------|-----------------------------------------|--------------------|
| `/*`      | Private S3 site bucket (OAC, SigV4)     | `CachingOptimized` |
| `/api/*`  | HTTP API (the `/api` prefix is stripped) | `CachingDisabled`  |

- **Same-origin API:** the browser calls `/api/files`, a CloudFront Function rewrites it to `/files`, and no CORS is needed.
- **Static export routing:** a second function maps `/x/` and `/x` to `/x/index.html`, since S3's REST endpoint has no directory indexes.
- **Runtime config:** Terraform writes `config.json` (`apiBase`, `cognitoDomain`, `clientId`, `redirectUri`, `logoutUri`, `region`) into the bucket with `Cache-Control: no-cache`, so one build works in any environment.
- **Security headers:** HSTS, CSP, nosniff, `X-Frame-Options: DENY`, strict referrer.
- **Errors:** only 404 maps to `/404.html`. A 403 is left alone so the API's RBAC denials reach the app as JSON.

Deploy the site (`--exclude` keeps `--delete` away from Terraform's `config.json`):

```sh
cd envs/dev
aws s3 sync ../../web/out "s3://$(terraform output -raw site_bucket)" --delete --exclude config.json
aws cloudfront create-invalidation --distribution-id "$(terraform output -raw distribution_id)" --paths '/*'
open "$(terraform output -raw site_url)"
```

## Observability (`modules/monitoring`)

CloudWatch alarms, an SNS alerts topic and an SLO dashboard (`terraform output slo_dashboard_url`).

| SLO          | Target                                         | Alarm                                |
|--------------|------------------------------------------------|--------------------------------------|
| Availability | 99.9% of API requests are not 5xx, per 5-minute window | `api-availability`: 2 of 3 windows over the 0.1% budget |
| Latency      | API p95 < 1 s                                  | `api-latency-p95`: 3 of 3 windows    |

Supporting alarms: Lambda `Errors` (per function, 2 of 3) and `Throttles` (any), and CloudFront `5xxErrorRate` > 5%.

- **Why 4xx don't count:** RBAC denials are 403s by design and bad input is 400. Those requests are the API working as intended, so only 5xx spend the error budget.
- **Low traffic:** windows with fewer than 10 requests count as 0% errors, and every alarm treats missing data as OK. A single failure on an idle lab can't page.
- **Where alerts go:** SNS topic `artifact-portal-dev-alerts`, for both ALARM and OK transitions. Email is subscribed only when `alert_email` is set: in an untracked `envs/dev/terraform.tfvars` locally, and as the `ALERT_EMAIL` repository **secret** in CI (masked in public logs; the variable is `sensitive`). Confirm the subscription from AWS's email.
- **No IAM changes:** the CI apply role's `PowerUserAccess` (`bootstrap/github_oidc.tf`) already covers CloudWatch and SNS, and this module creates no IAM roles.
- **Test the paging path** without breaking anything. The alarm flips back on its next evaluation, which also sends the OK notification:

```sh
aws cloudwatch set-alarm-state --alarm-name artifact-portal-dev-api-availability --state-value ALARM --state-reason test
```

## Frontend

`web/` is a Next.js static export (TypeScript, Tailwind, no server code). It signs in with the Cognito hosted UI (code + PKCE), mirrors the API's group permissions to decide what to show, and moves files straight between the browser and S3 via presigned URLs. The API still enforces every permission.

- **Config:** the app fetches `/config.json` at runtime (`apiBase`, `cognitoDomain`, `clientId`, `redirectUri`, `logoutUri`, `region`). Terraform writes the real file into the site bucket; `web/public/config.json` is a local-dev placeholder.
- **Local dev:** fill in `web/public/config.json`, then `cd web && npm install && npm run dev` (http://localhost:3000). `localhost:3000` must be in the Cognito client's callback/logout URLs and the API's CORS origins.
- **Deploy:** `scripts/deploy-web.sh` builds, syncs `web/out` to the site bucket (hashed assets cached for a year, HTML `no-cache`, `config.json` left alone) and invalidates CloudFront. Uses `AWS_PROFILE`, defaulting to `shua-labs-sso`.
