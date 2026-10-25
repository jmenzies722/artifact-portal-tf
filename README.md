# artifact-portal-tf

A serverless artifact distribution portal on AWS, built with Terraform: CloudFront, API Gateway, Cognito, Lambda, S3 and DynamoDB, with OIDC CI/CD, SLOs wired to PagerDuty, and zero-downtime secret rotation.

Personal lab project, written from scratch.

## Frontend

`web/` is a Next.js static export (TypeScript, Tailwind, no server code). It signs in with the Cognito hosted UI (code + PKCE), mirrors the API's group permissions to decide what to show, and moves files straight between the browser and S3 via presigned URLs. The API still enforces every permission.

- **Config:** the app fetches `/config.json` at runtime (`apiBase`, `cognitoDomain`, `clientId`, `redirectUri`, `logoutUri`, `region`). Terraform writes the real file into the site bucket; `web/public/config.json` is a local-dev placeholder.
- **Local dev:** fill in `web/public/config.json`, then `cd web && npm install && npm run dev` (http://localhost:3000). `localhost:3000` must be in the Cognito client's callback/logout URLs and the API's CORS origins.
- **Deploy:** `scripts/deploy-web.sh` builds, syncs `web/out` to the site bucket (hashed assets cached for a year, HTML `no-cache`, `config.json` left alone) and invalidates CloudFront. Uses `AWS_PROFILE`, defaulting to `shua-labs-sso`.
