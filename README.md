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

## Frontend

`web/` is a Next.js static export (TypeScript, Tailwind, no server code). It signs in with the Cognito hosted UI (code + PKCE), mirrors the API's group permissions to decide what to show, and moves files straight between the browser and S3 via presigned URLs. The API still enforces every permission.

- **Config:** the app fetches `/config.json` at runtime (`apiBase`, `cognitoDomain`, `clientId`, `redirectUri`, `logoutUri`, `region`). Terraform writes the real file into the site bucket; `web/public/config.json` is a local-dev placeholder.
- **Local dev:** fill in `web/public/config.json`, then `cd web && npm install && npm run dev` (http://localhost:3000). `localhost:3000` must be in the Cognito client's callback/logout URLs and the API's CORS origins.
- **Deploy:** `scripts/deploy-web.sh` builds, syncs `web/out` to the site bucket (hashed assets cached for a year, HTML `no-cache`, `config.json` left alone) and invalidates CloudFront. Uses `AWS_PROFILE`, defaulting to `shua-labs-sso`.
