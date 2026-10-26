# SRE review: artifact-portal-tf

Reviewed 2026-10-26 at `dcad31f` (main, clean tree). This was a read-only review: no code, Terraform, workflows or config changed, and nothing touched AWS.

## TL;DR

- **The roadmap is shipped, but it isn't finished.** Every feature the README lists exists in code. One user-facing path looks broken from the code alone: browser uploads need CORS on the artifacts bucket, and Terraform doesn't configure any (see [G1](#5-gaps--recommended-next-steps)).
- **Monitoring covers the API well and misses the rest.** The API SLOs (5xx availability, p95 latency) and the Lambda alarms are solid. Nothing alerts on S3 transfers, audit-write failures, rotation failures, DynamoDB, PagerDuty delivery, CloudFront 4xx (which includes a broken OAC) or total silence (there's no canary).
- **DR gaps:** the bootstrap Terraform state exists only on the laptop. Cognito users have no backup. Every data store has deletion protection off.

---

## 0. Checks run

| Check | Result |
|---|---|
| Read every file in `README.md`, `bootstrap/`, `envs/`, `modules/`, `lambda/`, `.github/workflows/`, `scripts/`, `web/src/` | Done |
| Searched for `TODO\|FIXME\|XXX\|TBD\|REPLACE_ME\|HACK\|changeme` (excluding `node_modules`, `.git`, build output) | Only hits are in `web/public/config.json` (`REPLACE_ME` x3). That's an intentional placeholder for local dev and is documented in the README |
| Searched for commented-out `resource`/`module`/`data` blocks | None |
| Roadmap items not checked off | README "Roadmap" says "Everything on the original roadmap has shipped". There's no TODO list or CHANGELOG |
| `python3 -m pytest -q` | **Not run.** The command needed approval, and this session couldn't get it. Indirect evidence: `.pytest_cache/v/cache/nodeids` lists **131** test IDs (last written 26 Oct 10:38) and `lastfailed` is `{}`, meaning the most recent local run had no failures |
| `terraform fmt -check -recursive` | **Not run** (needed approval). CI runs it on every PR (`.github/workflows/ci.yml`) |
| `terraform init -backend=false && terraform validate` (`envs/dev`, `bootstrap`) | **Not run** (needed approval) |
| `web`: lint / test / build | **Not run** (needed approval). `web/package.json` has **no `lint` and no `test` script**, only `dev`, `build` and `typecheck` |

To run them yourself (all read-only; `-lockfile=readonly` keeps the tracked `.terraform.lock.hcl` unchanged):

```sh
cd ~/Developer/projects/artifact-portal-tf
python3 -m pytest -q
terraform fmt -check -recursive
terraform -chdir=envs/dev  init -backend=false -lockfile=readonly -input=false && terraform -chdir=envs/dev  validate
terraform -chdir=bootstrap init -backend=false -lockfile=readonly -input=false && terraform -chdir=bootstrap validate
(cd web && npm ci && npm run typecheck && npm run build)
git status --porcelain   # next build has rewritten web/tsconfig.json before (commit 64f097c)
```

---

## 1. Completeness check

### Done

| Area | Evidence |
|---|---|
| Remote state: versioned, encrypted, TLS-only, S3-native lock | `bootstrap/main.tf`, `envs/dev/backend.tf` (`use_lockfile = true`) |
| GitHub OIDC: plan role for PRs (ReadOnly), apply role only for the `production` environment, pinned to immutable repo/owner IDs | `bootstrap/github_oidc.tf` |
| CI (PR): pytest, web build, fmt, validate, plan | `.github/workflows/ci.yml` |
| CD (main): tests, then approval gate (`environment: production`), then apply, then site publish | `.github/workflows/deploy.yml`, `scripts/deploy-web.sh` |
| Storage: CMK (rotation on), versioned bucket, TLS-only, deny wrong KMS key, lifecycle | `modules/storage/*.tf` |
| Auth: Cognito pool (admin-create-only, optional TOTP MFA, 12-char policy), 5 groups, PKCE web client, client-credentials CI client | `modules/auth/main.tf`, `clients.tf`, `m2m.tf` |
| API: HTTP API, JWT authorizer, 5 routes, one least-privilege role per Lambda, access logs, X-Ray, stage throttling | `modules/api/*.tf` |
| Server-side RBAC and path-traversal guard | `lambda/shared/permissions.py` |
| Immutable artifacts (`If-None-Match: *` signed into the PUT) | `lambda/upload_url/handler.py`, `lambda/tests/test_aws.py` |
| Audit trail: DynamoDB (KMS, PITR, TTL 90 days, `by_key` GSI), append-only IAM, `GET /activity` filtered by RBAC | `modules/api/audit.tf`, `modules/api/iam.tf`, `lambda/shared/audit.py`, `lambda/activity/handler.py` |
| CDN: OAC, two CloudFront Functions, security headers/CSP, only 404 mapped to an error page | `modules/cdn/*.tf`, `modules/cdn/functions/*.js` |
| Frontend: PKCE login, RBAC-driven sidebar, browse/upload/download/delete, activity panel | `web/src/lib/*.ts`, `web/src/components/files/*.tsx` |
| Observability: 13 alarms, SLO dashboard, SNS (email + PagerDuty) | `modules/monitoring/*.tf` |
| CI secret rotation (30 days, two-secret overlap) | `modules/auth/rotation.tf`, `lambda/rotate_ci_secret/handler.py`, `modules/auth/ROTATION.md` |

### Partly done

| Item | What's missing | Evidence |
|---|---|---|
| **Browser uploads** | No `aws_s3_bucket_cors_configuration` on the artifacts bucket. The UI does an XHR `PUT` to `https://<bucket>.s3.us-east-1.amazonaws.com/...` with custom headers, which forces a preflight. Without bucket CORS, the browser blocks it. The CSP allows S3 (`modules/cdn/headers.tf`), but CSP isn't CORS. Downloads still work because they're navigations (`window.open`). CI uploads (curl) also still work. That would explain why a CLI-driven e2e test passed. CORS may have been set by hand: run `aws s3api get-bucket-cors` (§4.3) to check | `web/src/lib/api.ts` (`putToS3`), `web/src/components/files/file-browser.tsx:127-140`, `\grep -rn cors --include='*.tf'` matches only API Gateway |
| Rotation | No alarm when rotation fails. ROTATION.md lists this under "Not done here". It also says the runtime's boto3 support for the multi-secret APIs is "Not verified locally", and that the first rotation must be run by hand. Nothing in the repo shows it was | `modules/auth/ROTATION.md` ("Not done here", "Runtime boto3", "First rotation") |
| End-to-end test | README claims "a scripted end-to-end check of people and machine access". No such script exists in the repo or its history. It's only mentioned in `lambda/tests/test_aws.py` and in commit `6ca373c` | `README.md:17`, `scripts/` (only `deploy-web.sh`), `git log --diff-filter=D` |
| Frontend quality gates | No lint script and no tests. The `typecheck` script exists, but CI never calls it | `web/package.json`, `.github/workflows/ci.yml` |
| Deploy pipeline | Apply re-plans instead of applying the plan reviewed on the PR. The site is built *after* `terraform apply`, so a web build failure leaves infra deployed and the site stale. No smoke test runs after deploy, and there's no automated rollback | `.github/workflows/deploy.yml` |
| PagerDuty | `envs/dev/main.tf` says the secret is "Created by hand (see README)", but the README has no creation steps. If the secret is missing, **every plan and apply fails**, because the data source errors | `envs/dev/main.tf:67`, `modules/monitoring/pagerduty.tf` |
| Docs drift | `envs/dev/variables.tf` says `ALERT_EMAIL` is a "repository variable", but the workflows read `secrets.ALERT_EMAIL`. ROTATION.md says "The README isn't updated", but it now is | `envs/dev/variables.tf:2`, `.github/workflows/*.yml`, `modules/auth/ROTATION.md` |
| Lambda throttle alarm | Its description says it catches "the stage's rate limit". It can't: API Gateway answers stage throttling with 429 before Lambda is invoked, so `AWS/Lambda Throttles` never moves | `modules/monitoring/alarms_lambda.tf:24-25`, `modules/api/stage.tf` |
| Runtime parity | CI tests on Python 3.12, but the Lambdas run 3.13 | `.github/workflows/*.yml`, `modules/api/lambda.tf` |

### Missing

| Item | Evidence |
|---|---|
| Prod environment (`envs/prod` is just `.gitkeep`). The GitHub environment called `production` actually deploys **dev** | `envs/prod/.gitkeep`, `deploy.yml` |
| Remote state for `bootstrap/`. It has no backend block, and `bootstrap/terraform.tfstate` lives only on local disk (gitignored) | `bootstrap/` (no `backend.tf`), `.gitignore` |
| Synthetic canary, burn-rate alarms, DynamoDB / SNS-delivery / audit-failure / CloudFront-4xx alarms, AWS Budgets | `modules/monitoring/` |
| WAF, CloudFront access logs, CloudTrail S3 data events (the only record that a transfer actually happened) | `modules/cdn/distribution.tf`, `modules/storage/` |
| Backups beyond PITR and versioning (AWS Backup, Cognito user export), deletion protection | `modules/api/audit.tf:11`, `modules/auth/main.tf:5`, `modules/storage/main.tf:78` |

---

## 2. What it produces

### Resources (dev, `envs/dev/main.tf`, prefix `artifact-portal-dev`)

| Module | Resources |
|---|---|
| bootstrap (separate root) | State bucket `artifact-portal-tfstate-755484097925`, GitHub OIDC provider, roles `artifact-portal-gha-plan` / `artifact-portal-gha-apply` |
| storage | KMS CMK + `alias/artifact-portal-dev-artifacts`, artifacts bucket (versioned, SSE-KMS, `develop/` moves to IA after 30 days, noncurrent versions expire after 30 days) |
| auth | User pool, 5 groups, hosted-UI domain, resource server (`artifacts/read`, `artifacts/write`), web client (PKCE), CI client (secret), Secrets Manager `artifact-portal-dev/ci-client`, rotation Lambda + role + log group |
| api | HTTP API, JWT authorizer, 5 routes/integrations, `$default` stage (10 rps / burst 20, JSON access logs), 5 Lambdas (py3.13, arm64, 128 MB, 10 s timeout, X-Ray), 5 roles, 6 log groups (14 days), DynamoDB `artifact-portal-dev-audit` |
| cdn | CloudFront distribution (PriceClass_100, HTTP/2+3), OAC, 2 CloudFront Functions, response-headers policy, private site bucket (versioned, SSE-S3), `config.json` object |
| monitoring | SNS `artifact-portal-dev-alerts` + topic policy, email subscription (optional) and PagerDuty HTTPS subscription, 13 alarms, dashboard `artifact-portal-dev-slo` |

### Request path

```
                         ┌──────────────── Cognito hosted UI (PKCE) ──────────────┐
                         │  /oauth2/authorize, /oauth2/token  → JWT (1h access)   │
                         └──────────────▲─────────────────────────────────────────┘
                                        │
 Browser ──HTTPS──► CloudFront d77vjbj8h7gd5.cloudfront.net  (security headers on all)
   │                 │
   │                 ├─ /*      ─ CF Fn rewrite_index ─► S3 site bucket (OAC/SigV4, private)
   │                 │                                   index.html, _next/static, config.json
   │                 │
   │                 └─ /api/*  ─ CF Fn strip_api_prefix ─► API Gateway HTTP API ($default)
   │                                                        │ JWT authorizer (web + CI client ids)
   │                                                        ├─ GET    /files    ─► λ list-files   ─► S3 ListBucket
   │                                                        ├─ POST   /upload   ─► λ upload-url   ─► presign PUT ─┐
   │                                                        ├─ GET    /download ─► λ download-url ─► HeadObject + presign GET
   │                                                        ├─ DELETE /files    ─► λ delete-file  ─► DeleteObject (marker)
   │                                                        └─ GET    /activity ─► λ activity     ─► DynamoDB Query
   │                                                                upload/download/delete ─► DynamoDB PutItem (audit, best effort)
   │
   └──── presigned PUT/GET (5 min, SigV4, SSE-KMS) ───────► S3 artifacts bucket (CMK)   ◄── NOT behind CloudFront,
                                                                                            NOT in any metric/alarm
 CI system ──client_credentials──► Cognito /oauth2/token ──► same /api/upload path (scope artifacts/write)

 Alarms (CloudWatch) ──► SNS artifact-portal-dev-alerts ──► email (if alert_email set)
                                                       └──► PagerDuty CloudWatch integration (service artifact-portal-dev)
```

### Auth / RBAC model

- **People:** Cognito users (admin-created only), each in a group. The API reads `cognito:groups` from the access token's claims. `lambda/shared/permissions.py` maps each group to an action and the key prefixes it may use. `web/src/lib/rbac.ts` mirrors those rules, but only to decide what to show.
- **Machines:** a token with `client_id`, no `username` and no groups counts as a machine. Its OAuth scopes map to prefixes (`SCOPE_RULES`).
- **Order of checks:** an unauthenticated request gets 401. A bad key/prefix (leading `/` or `..`) gets 400. A request that isn't allowed gets 403. Download authorizes **before** `HeadObject`, so a 404 can't reveal what exists outside the caller's prefixes.
- Decisions are logged to CloudWatch as JSON (`http.log_request`). Allowed actions are also written to DynamoDB.

### CI/CD flow

```
PR ──► ci.yml: pytest(3.12) ∥ web build ∥ [fmt → OIDC(plan role) → init → validate → plan → step summary]
merge to main ──► deploy.yml: pytest ──► ⏸ approval (env "production", main only)
                  ──► OIDC(apply role) ──► terraform apply -auto-approve ──► scripts/deploy-web.sh
                       (npm ci/build → sync _next/static immutable → sync rest no-cache --delete, excl. config.json
                        → CloudFront invalidation /*)
```

### Observability stack

- CloudWatch metrics, alarms and dashboard. API Gateway access logs. Lambda logs (14 days). X-Ray (active tracing on all 5 API Lambdas).
- Notifications go through SNS to email and PagerDuty. Both ALARM and OK transitions are sent, so OK auto-resolves the PagerDuty incident.

---

## 3. What a user can do

Taken from `lambda/shared/permissions.py` and `web/src/components/files/*.tsx`.

| Principal | list | read (download) | write (upload) | delete | `/activity` |
|---|---|---|---|---|---|
| `developers` | public/, partners/, develop/ | same | same | same | yes |
| `operations` | public/, partners/ | same | same | same | yes |
| `testers` | public/, partners/ | public/, partners/ | – | – | yes |
| `partner_a` / `partner_b` | public/, own `partners/partner_x/` | same | own folder only | **– (can't delete own uploads)** | yes (own folders) |
| CI client (`artifacts/write`) | – | – | develop/, public/ | – | 403 |
| `artifacts/read` scope | Defined in Cognito and `SCOPE_RULES`, but **no client is granted it** | | | | |

Features in the UI:

- Sign in and out through the Cognito hosted UI (PKCE). Tokens stay in `sessionStorage`, and the 12 h refresh token keeps the session alive.
- The sidebar lists the folders each role can see, with a "Read & write" or "Read only" label.
- Users can browse folders and filter files by name.
- Multi-file and drag-and-drop upload into the current folder, with progress. Re-uploading an existing key returns 412 ("Artifacts are immutable"). A single presigned PUT is capped at 5 GB, and the URL expires after 5 minutes.
- Download opens a presigned GET (5 min) in a new tab.
- Delete asks for confirmation. On the versioned bucket it adds a delete marker, so the object can be restored for 30 days.
- "Recent activity" panel (24 h or 7 days, up to 100 items). Each user sees only keys they may list. Other users' IPs and groups are never shown.
- There's **no admin UI.** Creating users and assigning groups is done in the Cognito console or CLI.

---

## 4. SRE test plan (dev)

### 4.0 Setup (run from repo root)

```sh
export AWS_PROFILE=shua-labs-sso AWS_REGION=us-east-1
tfo() { terraform -chdir=envs/dev output -raw "$1"; }
P=artifact-portal-dev
SITE=$(tfo site_url); DIST=$(tfo distribution_id); TOPIC=$(tfo alerts_topic_arn)
BUCKET=$(tfo artifacts_bucket); SITE_BUCKET=$(tfo site_bucket)
CI_SECRET=$(tfo ci_secret_arn); LOGIN=$(tfo hosted_login_domain)

# Machine token (artifacts/write). Fetch once and reuse it: it lasts 1 h.
CREDS=$(aws secretsmanager get-secret-value --secret-id "$CI_SECRET" --query SecretString --output text)
CI_TOKEN=$(curl -s -u "$(jq -r .client_id <<<"$CREDS"):$(jq -r .client_secret <<<"$CREDS")" \
  -d 'grant_type=client_credentials&scope=artifacts/write' "$LOGIN/oauth2/token" | jq -r .access_token)

# Human token. Sign in at $SITE as a dedicated `testers` user, then run this in the DevTools console:
#   JSON.parse(sessionStorage.getItem('ap.session')).accessToken
export USER_TOKEN='<paste>'
```

### 4.1 SLIs / SLOs defined in code

| Alarm (exact name) | SLI | Threshold | Period / eval | Gate | Missing data |
|---|---|---|---|---|---|
| `artifact-portal-dev-api-availability` | API `5xx / Count` | > 0.1% (SLO 99.9% non-5xx) | 300 s, 2 of 3 | `Count >= 10` | notBreaching |
| `artifact-portal-dev-api-latency-p95` | API `Latency` p95 | > 1000 ms | 300 s, 3 of 3 | `Count >= 10` | notBreaching |
| `artifact-portal-dev-cloudfront-5xx` | CF `5xxErrorRate` avg | > 5% | 300 s, 2 of 3 | `Requests >= 10` | notBreaching |
| `artifact-portal-dev-lambda-errors-{activity,delete_file,download_url,list_files,upload_url}` | Lambda `Errors` | > 0 | 300 s, 2 of 3 | none | notBreaching |
| `artifact-portal-dev-lambda-throttles-{same 5}` | Lambda `Throttles` | > 0 | 300 s, 1 of 1 | none | notBreaching |

Source: `modules/monitoring/alarms_*.tf`, `variables.tf` (`availability_target = 99.9`, `latency_p95_ms = 1000`).

Gaps:

1. **No burn-rate alarms.** Once the gate is passed, 0.1% per 5-minute window means **any single 5xx in 2 of 3 windows pages.** That's a static threshold, not an error budget. The usual fix is multi-window burn-rate alarms, e.g. 14.4x over 1 h and 5 m, plus 6x over 6 h and 30 m, against a 30-day budget.
2. **No synthetic canary.** With the low-traffic gate and `notBreaching`, an idle portal that's fully down raises **no alarm at all.**
3. **429s and authorizer 401s are invisible.** They're 4xx, so they never count against the SLO. Stage throttling never reaches Lambda either, so the throttle alarms can't see it.
4. **S3 transfers aren't measured.** The presigned PUT/GET goes browser → S3 directly. If KMS, IAM or CORS breaks, the API still returns 200 and every SLI stays green.
5. **No CloudFront 4xx alarm.** A broken OAC or bucket policy shows up as S3 403s, and S3 serves 404 if `index.html` is deleted. Neither alerts.
6. **Uncovered components:** the rotation Lambda, DynamoDB (`ThrottledRequests`, `SystemErrors`), the `audit_write_failed` log line (no metric filter), and SNS `NumberOfNotificationsFailed`.
7. **No latency SLO for the static site**, and no p99.

### 4.2 Monitoring and alerting verification

**a. Inventory and subscription health**

```sh
aws cloudwatch describe-alarms --alarm-name-prefix "$P-" \
  --query 'MetricAlarms[].[AlarmName,StateValue,ActionsEnabled]' --output table      # expect 13 rows, OK, True
aws sns list-subscriptions-by-topic --topic-arn "$TOPIC" \
  --query 'Subscriptions[].[Protocol,SubscriptionArn]' --output table                # neither may say PendingConfirmation
aws secretsmanager describe-secret --secret-id "$P/pagerduty-cloudwatch-url" --query '[Name,LastChangedDate]'
```

**b. Fire one alarm end to end** (expect one email and one PagerDuty incident on `artifact-portal-dev`; the next evaluation, within about 5 minutes, sends OK and resolves it):

```sh
T0=$(date -u +%FT%TZ)
aws cloudwatch set-alarm-state --alarm-name "$P-api-availability" --state-value ALARM --state-reason "SRE drill $T0"
aws cloudwatch describe-alarm-history --alarm-name "$P-api-availability" --history-item-type Action \
  --start-date "$T0" --query 'AlarmHistoryItems[].HistorySummary'                    # "Successfully executed action arn:aws:sns:..."
aws cloudwatch get-metric-statistics --namespace AWS/SNS --dimensions Name=TopicName,Value="$P-alerts" \
  --metric-name NumberOfNotificationsFailed --start-time "$T0" --end-time "$(date -u -v+15M +%FT%TZ)" \
  --period 300 --statistics Sum                                                      # expect 0 / no datapoints
```

Pass when the email arrives, a PagerDuty incident opens with the alarm name, and the incident auto-resolves on OK. Check PagerDuty in its UI. The PagerDuty MCP connector isn't authorized on this machine.

**c. All alarms** (this opens 13 incidents, so warn your on-call first, even if that's only you):

```sh
for a in $(aws cloudwatch describe-alarms --alarm-name-prefix "$P-" --query 'MetricAlarms[].AlarmName' --output text); do
  aws cloudwatch set-alarm-state --alarm-name "$a" --state-value ALARM --state-reason "SRE drill"; sleep 10
done
```

**d. Real-signal test.** `set-alarm-state` only proves the notification path. To prove the *metric math*, cause real 5xx with Lambda-error injection (§4.3, row 2), using the k6 script at 1 rps so the `Count >= 10` gate is cleared.

**e. Dashboard.** Open `$(tfo slo_dashboard_url)` during the k6 run. All 7 widgets should populate, and the "Alarm status" widget should list 13 alarms. Note that the rotation Lambda isn't on the dashboard.

### 4.3 Failure modes

Smoke checks (no auth needed). Run these before and after every injection:

```sh
curl -s -o /dev/null -w 'site %{http_code}\n'  "$SITE/"            # 200
curl -s -o /dev/null -w 'api  %{http_code}\n'  "$SITE/api/files"   # 401 (JWT authorizer), proves CF→APIGW
curl -sI "$SITE/config.json" | \grep -i -E 'cache-control|x-cache'   # no-cache
aws s3api get-bucket-cors --bucket "$BUCKET"                         # NoSuchCORSConfiguration ⇒ G1: browser uploads broken
```

| # | Failure | Expected behavior | How to inject (dev) | Alert that should fire | Recovery |
|---|---|---|---|---|---|
| 1 | **Site origin (S3) unavailable** | Deleting `index.html` gives a 404 page. A policy/OAC break gives S3 403s | `aws s3 rm "s3://$SITE_BUCKET/index.html"` then `aws cloudfront create-invalidation --distribution-id $DIST --paths /index.html /` | **None** (4xx). `cloudfront-5xx` only fires if the origin is unreachable. **Gap** | `./scripts/deploy-web.sh`, or restore the previous version: `aws s3api list-object-versions --bucket $SITE_BUCKET --prefix index.html`, then delete the delete marker |
| 2 | **Lambda errors** | API returns 500 for that route. Other routes are unaffected | `aws lambda update-function-configuration --function-name $P-list-files --environment "Variables={BUCKET_NAME=does-not-exist-$RANDOM,KMS_KEY_ARN=x,AUDIT_TABLE=x}"`, then drive about 1 rps for 15 minutes | `lambda-errors-list_files` (about 10 min), `api-availability` (if ≥10 req per window), `cloudfront-5xx` (if 5xx > 5% of CF requests) | `terraform -chdir=envs/dev apply` (or re-run Deploy). Terraform reverts the env drift |
| 3 | **Lambda throttling** | Callers get 5xx/429 from API Gateway. Record which status HTTP API returns here | `aws lambda put-function-concurrency --function-name $P-list-files --reserved-concurrent-executions 0`, then send a few requests | `lambda-throttles-list_files` (1 datapoint), maybe `api-availability` | `aws lambda delete-function-concurrency --function-name $P-list-files` |
| 3b | **Stage throttling** | 429 "Too Many Requests". The UI shows "Too many requests…" | k6 spike scenario (§4.4) at about 25 rps | **None** (4xx, and Lambda is never invoked). **Gap** | Stops when the load stops |
| 4 | **Audit write fails (DynamoDB throttle, KMS, or IAM)** | Upload, download and delete still succeed by design. Logs show `{"msg":"audit_write_failed"}`. `/activity` misses the event | `aws iam put-role-policy --role-name $P-upload-url --policy-name sre-chaos-deny-audit --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Deny","Action":"dynamodb:PutItem","Resource":"*"}]}'`, then `POST /api/upload` with `$CI_TOKEN` | **None.** No metric filter exists. **Gap.** Confirm with Logs Insights: `filter msg="audit_write_failed" \| stats count() by bin(5m)` on `/aws/lambda/$P-upload-url` | `aws iam delete-role-policy --role-name $P-upload-url --policy-name sre-chaos-deny-audit`. **Terraform won't remove it**, because it doesn't track extra inline policies |
| 5 | **S3 transfer fails after a successful presign** | API 200, then the browser PUT gets 403 | `aws iam put-role-policy --role-name $P-upload-url --policy-name sre-chaos-deny-put --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Deny","Action":"s3:PutObject","Resource":"*"}]}'`, then upload through the UI or curl | **None.** **Gap**: transfers are unobserved | `aws iam delete-role-policy --role-name $P-upload-url --policy-name sre-chaos-deny-put` |
| 6 | **Rotated CI secret, happy path** | The new secret is AWSCURRENT and the old one still works (AWSPREVIOUS) | `aws secretsmanager rotate-secret --secret-id "$CI_SECRET"`, then `aws logs tail /aws/lambda/$P-rotate-ci-secret --since 10m`, then fetch tokens with the **AWSCURRENT and AWSPREVIOUS** credentials (`get-secret-value --version-stage AWSPREVIOUS`). Both must return 200 | n/a | n/a. **Never run two rotations back to back** (ROTATION.md, grace-period caveat) |
| 6b | **Rotation fails** | AWSCURRENT is unchanged, and an AWSPENDING version is left behind. CI keeps working | `aws lambda update-function-configuration --function-name $P-rotate-ci-secret --environment "Variables={USER_POOL_ID=<id>,CLIENT_ID=<id>,TOKEN_URL=https://invalid.example/oauth2/token,SCOPE=artifacts/write}"`, then `rotate-secret` | **None.** The rotation Lambda isn't in `function_names`. **Gap** | `terraform apply` (restores env), then remove the stuck stage: `aws secretsmanager update-secret-version-stage --secret-id "$CI_SECRET" --version-stage AWSPENDING --remove-from-version-id <id>`, then rotate again |
| 7 | **Bad deploy (code)** | 5xx on the affected route right after approval | Throwaway PR that adds `raise RuntimeError("sre drill")` in `lambda/activity/handler.py`. Merge it, approve, and open the activity panel | `lambda-errors-activity`, `api-availability` | `git revert -m 1 <merge>`, then PR, merge and approve. There are no Lambda aliases or versions, so **revert-forward is the only rollback** |
| 7b | **Bad deploy (web build fails after apply)** | Infra updated, site stale. The Deploy job turns red | (Observe it; don't inject) | GitHub Actions failure email only | Fix forward, or `workflow_dispatch` Deploy |
| 8 | **CloudFront cache misbehavior** | HTML and `config.json` revalidate. `_next/static` is immutable. `/api/*` is never cached | `for p in / /files/ /config.json /api/files; do curl -sI "$SITE$p" \| \grep -i -E '^(HTTP\|x-cache\|cache-control\|age)'; done`. To inject: `aws s3 cp web/out/index.html s3://$SITE_BUCKET/index.html --cache-control 'max-age=86400'` | None. **Gap**: no content check | Re-run `deploy-web.sh` (restores `no-cache`) plus invalidate `/*` |
| 9 | **IAM/OIDC misconfiguration** | Deploy fails at `configure-aws-credentials` with `Not authorized to perform sts:AssumeRoleWithWebIdentity`, before any change to AWS | Negative test on a throwaway branch: a PR workflow that tries `role-to-assume: …gha-apply` must **fail**. Check that `gha-plan` can't write: `aws sts assume-role…` isn't possible locally, so read the CloudTrail `AssumeRoleWithWebIdentity` events instead | GitHub failure email only | Fix `bootstrap/github_oidc.tf` and apply **locally** (bootstrap isn't in CI) |
| 10 | **PagerDuty integration URL invalid** | SNS HTTPS delivery fails after retries. Email still arrives | Disable the integration in PagerDuty (reversible) rather than editing the secret, then `set-alarm-state` (§4.2b) | **None.** Watch `AWS/SNS NumberOfNotificationsFailed`. **Gap** | Re-enable it, or create a new integration, then `aws secretsmanager put-secret-value --secret-id $P/pagerduty-cloudwatch-url --secret-string '<url>'`, then apply (the subscription endpoint changes) |
| 10b | **PagerDuty secret deleted** | **Every `terraform plan`/`apply` fails** (data source not found), which blocks all deploys | Don't inject. Reason about it from `modules/monitoring/pagerduty.tf` | n/a | Recreate the secret. A planned fix would be a `try()` or a boolean feature flag |
| 11 | **KMS key disabled or scheduled for deletion** | Uploads and downloads fail at S3. The audit table becomes inaccessible | **Don't inject** (risks the table becoming inaccessible). Use rows 4 and 5 instead | None | `aws kms enable-key` / `cancel-key-deletion` (7-day window) |

### 4.4 Load testing

**Limits to respect** (from code, plus AWS defaults to check):

- **API stage throttle:** 10 rps steady with a burst of 20, set in `default_route_settings` (`modules/api/stage.tf`). Requests above that get 429. HTTP API applies default route settings per route, so confirm the effective behavior with the spike scenario.
- **Lambda:** no reserved concurrency, 128 MB, 10 s timeout. Check the account limit with `aws lambda get-account-settings --query AccountLimit.ConcurrentExecutions`. New accounts can be as low as 10. At 8 rps × ~200 ms you need about 2 concurrent, so this isn't a bottleneck.
- **DynamoDB:** on-demand. Every write for a day goes to **one partition key** (`DAY#YYYY-MM-DD`), which is a hot-key ceiling of about 1,000 WCU/s per partition. That's irrelevant under the 10 rps API cap, but it matters if the cap is ever raised.
- **Cognito:** client-credentials token requests are billed per request, and user-pool API quotas apply. Fetch tokens **once** (as in §4.0), never per iteration.

**Pass criteria (tied to the SLOs):** p95 < 1000 ms, 5xx rate < 0.1%, zero 429s below 10 rps, checks > 99%. The `api-latency-p95` and `api-availability` alarms must stay OK for the whole run.

**Profile:** 2 min baseline at 2 rps, a 3 min ramp to 8 rps, 10 min soak at 8 rps, then ramp down. The optional spike runs 25 rps for 60 s and is expected to produce 429s and **no** 5xx. Traffic goes through CloudFront, so the edge, the function rewrite and API Gateway are all measured. Don't hit the `execute-api` URL directly.

`loadtest/portal.js` (keep it outside the repo, or add it in a separate PR):

```js
// k6 run -e BASE_URL=$SITE -e ACCESS_TOKEN=$USER_TOKEN -e DOWNLOAD_KEY=public/readme.txt portal.js
// k6 run -e SPIKE=1 ...   # throttle verification: expects 429s, zero 5xx
import http from 'k6/http';
import { check } from 'k6';
import { Rate, Counter } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'https://d77vjbj8h7gd5.cloudfront.net';
const AUTH = { headers: { Authorization: `Bearer ${__ENV.ACCESS_TOKEN}` } };
const KEY = __ENV.DOWNLOAD_KEY || 'public/readme.txt';
const SPIKE = __ENV.SPIKE === '1';

const server5xx = new Rate('server_5xx');
const throttled = new Counter('throttled_429');

// 403/429 are "expected" here so http_req_failed reflects real failures only.
http.setResponseCallback(http.expectedStatuses({ min: 200, max: 399 }, 403, 429));

const steady = {
  baseline: { executor: 'constant-arrival-rate', rate: 2, timeUnit: '1s', duration: '2m',
              preAllocatedVUs: 5, maxVUs: 20 },
  ramp: { executor: 'ramping-arrival-rate', startTime: '2m', startRate: 2, timeUnit: '1s',
          preAllocatedVUs: 10, maxVUs: 40,
          stages: [{ target: 8, duration: '3m' }, { target: 8, duration: '10m' }, { target: 0, duration: '1m' }] },
};
const spike = {
  spike: { executor: 'constant-arrival-rate', rate: 25, timeUnit: '1s', duration: '60s',
           preAllocatedVUs: 30, maxVUs: 60 },
};

export const options = {
  scenarios: SPIKE ? spike : steady,
  thresholds: SPIKE
    ? { server_5xx: ['rate==0'], throttled_429: ['count>0'] }
    : {
        'http_req_duration{scenario:ramp}': ['p(95)<1000'],   // latency SLO
        server_5xx: ['rate<0.001'],                            // availability SLO
        throttled_429: ['count==0'],                           // below the stage limit
        checks: ['rate>0.99'],
      },
};

export default function () {
  const r = Math.random();
  let res;
  if (r < 0.7) res = http.get(`${BASE}/api/files?prefix=public/`, { ...AUTH, tags: { route: 'list' } });
  else if (r < 0.9) res = http.get(`${BASE}/api/activity?days=1`, { ...AUTH, tags: { route: 'activity' } });
  else res = http.get(`${BASE}/api/download?key=${encodeURIComponent(KEY)}`, { ...AUTH, tags: { route: 'download' } });
  // Never follow the presigned URL: that would be S3 egress, not an API test.

  server5xx.add(res.status >= 500);
  if (res.status === 429) throttled.add(1);
  if (!SPIKE) check(res, { '2xx': (x) => x.status >= 200 && x.status < 300 });
}
```

Quick alternative: `hey -z 2m -c 4 -q 2 -H "Authorization: Bearer $USER_TOKEN" "$SITE/api/files?prefix=public/"`. Here `-q` is per worker, so this sends about 8 rps.

**Cautions:**

- The access token lasts 1 hour, so keep each run under about 55 minutes.
- Every `/download` call writes an audit item, so the activity feed and the `by_key` index fill with load-test noise for 90 days. Run as a `testers` user against one known key, and don't use `/upload` (which also writes audit items).
- **Cost:** about 8–10k requests per run. That works out to roughly $0.01 for API Gateway, with Lambda, DynamoDB and CloudWatch Logs in the cents. X-Ray stays inside the free tier at this volume. The real risk is following presigned URLs to large objects (S3 egress at about $0.09/GB), or leaving a spike running.
- Tell PagerDuty first. A badly tuned run *should* page you.

### 4.5 Recovery / DR

| Asset | Protection in code | Recovery procedure | RPO | RTO (estimate) |
|---|---|---|---|---|
| Dev Terraform state | S3 versioning, 90-day noncurrent retention, SSE, S3-native lock (`bootstrap/main.tf`, `envs/dev/backend.tf`) | `aws s3api list-object-versions --bucket artifact-portal-tfstate-755484097925 --prefix dev/terraform.tfstate`, then `get-object --version-id <v> old.tfstate`, then `terraform -chdir=envs/dev state push old.tfstate`. For a stale lock: `terraform force-unlock <id>` | Last apply | ~15 min |
| **Bootstrap state** | **None.** Local file only, gitignored | Re-import the state bucket, OIDC provider and both roles with `terraform import` | Unbounded | 1–2 h |
| Lambda code / API / CDN config | Git (remote: GitHub) | `git revert` the merge, then PR, merge, approve, deploy. No Lambda versions or aliases exist | 0 | 10–20 min (approval-bound) |
| Static site | Site bucket versioning (no lifecycle, so old versions are kept forever) and git | Re-run Deploy for a known-good commit, or `deploy-web.sh` locally | 0 | 5–10 min, plus invalidation |
| Artifacts | Versioning, noncurrent versions kept 30 days. **`force_destroy = true`**, no replication, no AWS Backup | Undelete: `aws s3api list-object-versions --bucket $BUCKET --prefix <key>`, then `aws s3api delete-object --bucket $BUCKET --key <key> --version-id <delete-marker-id>` | 0 for deletes (≤30 days). **Total loss** on `terraform destroy` or region loss | Minutes per object |
| Audit table | **PITR on** (`modules/api/audit.tf`), TTL 90 days. Deletion protection **off** | `aws dynamodb restore-table-to-point-in-time --source-table-name $P-audit --target-table-name $P-audit-restored --restore-date-time <ts> --sse-specification-override Enabled=true,SSEType=KMS,KMSMasterKeyId=alias/$P-artifacts`. Then either point `AUDIT_TABLE` at the restored table or copy items back. The restored table doesn't keep TTL or PITR, so re-enable them. A deleted table leaves a 35-day system backup | ~5 min (PITR) | 30–60 min |
| Cognito users and groups | **None.** `deletion_protection = "INACTIVE"` | No native backup. If the pool is replaced, every user must be re-invited and every password and MFA device is lost | Total | Hours (manual) |
| CI client secret | Secrets Manager versions (AWSPREVIOUS), plus a second live Cognito secret | Point CI at AWSPREVIOUS, or `rotate-secret` | 0 | Minutes |
| KMS CMK | 7-day deletion window, automatic rotation | `aws kms cancel-key-deletion` / `enable-key` | n/a | Minutes. Losing the key means losing all artifacts and the audit table |

Drill this quarterly. A PITR restore of the audit table to a scratch name times the RTO, then delete the scratch table. Undelete one artifact. Restore one prior state version to a local file (don't `state push` unless you have to).

### 4.6 Chaos ideas (safe for a personal lab)

**Ground rules:** inject one fault at a time, in a quiet window, with a written start and stop. Before and after, run §4.3's smoke checks and a `terraform -chdir=envs/dev plan`. The plan should show only the drift you injected.

1. **Alarm path game day.** Run §4.2b/c monthly. It's zero risk and tests the PagerDuty path.
2. **Throttle a single function.** §4.3 #3. Easy to reverse.
3. **Error injection on one route.** §4.3 #2. Proves the gated metric math with real traffic from k6 at 1–2 rps.
4. **Silent-failure drills.** §4.3 #4 and #5. These demonstrate the gaps. Re-run them after adding the missing alarms to confirm the alarms catch them.
5. **Latency.** `aws lambda update-function-configuration --function-name $P-download-url --timeout 1` plus k6 for 15 minutes. Expect timeouts, which show up as Lambda `Errors` and API 5xx. Revert with apply.
6. **Rotation under load.** Run `rotate-secret` while a loop requests CI tokens every 5 seconds. Expect zero token failures.
7. **AWS FIS (optional).** FIS has Lambda actions (`aws:lambda:invocation-add-delay`, `aws:lambda:invocation-error`), but they need the FIS extension layer and config on each function, which is a Terraform change. They're billed per action-minute. The manual injections above get you 90% of the value for $0.

**Don't** disable the KMS key, delete the PagerDuty secret, or touch the bootstrap roles.

---

## 5. Gaps & recommended next steps

Highest priority first.

| # | Priority | Recommendation |
|---|---|---|
| G1 | **P0** | Run `aws s3api get-bucket-cors` and a real browser upload. If CORS is missing, add `aws_s3_bucket_cors_configuration` (PUT/GET from the CloudFront origin and `localhost:3000`, with the four signed headers allowed). |
| G2 | P1 | Move `bootstrap/` state to the remote state bucket (separate key), or at least back it up, because it's currently the only copy of that state. |
| G3 | P1 | Add a CloudWatch Synthetics canary (or a scheduled GitHub Action) that loads `/` and calls `/api/files` with a machine token every 5 minutes, so the idle portal can detect a total outage. |
| G4 | P1 | Add a metric filter and alarm on `audit_write_failed`, plus alarms on DynamoDB `SystemErrors`/`ThrottledRequests` for the audit table. |
| G5 | P1 | Alarm on rotation failure (`lambda-errors` for `$P-rotate-ci-secret`, or the EventBridge `RotationFailed` event). Then run and record the first manual rotation. |
| G6 | P1 | Alarm on SNS `NumberOfNotificationsFailed` for the alerts topic, so a broken PagerDuty integration can't fail silently. |
| G7 | P2 | Replace the static 5xx threshold with multi-window burn-rate alarms against a 30-day error budget. |
| G8 | P2 | Add a gated alarm on CloudFront `4xxErrorRate` and API `4xx` share (with 429 as its own signal), because origin/OAC breakage and throttling are invisible today. |
| G9 | P2 | Make the PagerDuty data source optional (`try()` or a boolean flag), so a missing secret can't block every deploy, and document how to create the secret. |
| G10 | P2 | Add a post-deploy smoke test step (`curl /` → 200, `/api/files` → 401, `/config.json` valid) to `deploy.yml`, and build the web bundle *before* `terraform apply`. |
| G11 | P2 | Commit the end-to-end script the README mentions, or drop the claim. |
| G12 | P2 | Turn on CloudTrail S3 data events (or S3 server access logs) for the artifacts bucket, so completed transfers, not just issued URLs, are auditable. |
| G13 | P3 | Turn on deletion protection for the audit table and user pool, and set `force_destroy = false` on the artifacts bucket, before calling anything production-like. |
| G14 | P3 | Add `npm run typecheck` (plus a lint script) to CI and pin CI Python to 3.13 to match the runtime. |
| G15 | P3 | Fix the doc drift: the `ALERT_EMAIL` "variable" vs secret wording, ROTATION.md's "README isn't updated", and the throttle alarm description's claim about the stage limit. |
| G16 | P3 | Add an AWS Budgets alert on the account, so a runaway load test or abuse of the public site gets noticed. |
