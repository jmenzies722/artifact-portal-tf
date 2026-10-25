#!/usr/bin/env bash
# Build the static frontend and publish it to the site bucket behind CloudFront.
# config.json is never touched: Terraform owns it in the bucket.
set -euo pipefail

cd "$(dirname "$0")/.."
# Locally use your SSO profile; in CI, OIDC credentials are already in the env.
if [ -z "${CI:-}" ]; then export AWS_PROFILE="${AWS_PROFILE:-shua-labs-sso}"; fi

BUCKET="$(terraform -chdir=envs/dev output -raw site_bucket)"
DISTRIBUTION_ID="$(terraform -chdir=envs/dev output -raw distribution_id)"

(cd web && npm ci && npm run build)

# 1. Hashed build assets first, so new HTML never points at a missing file.
#    No --delete here: tabs still running the previous build keep working.
aws s3 sync web/out/_next/static "s3://$BUCKET/_next/static" \
  --cache-control "public, max-age=31536000, immutable"

# 2. HTML and everything else: always revalidated.
aws s3 sync web/out "s3://$BUCKET" --delete \
  --exclude config.json \
  --exclude "_next/static/*" \
  --cache-control "no-cache"

aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths "/*" \
  --query "Invalidation.Id" --output text
