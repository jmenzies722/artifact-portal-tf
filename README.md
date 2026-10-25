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
