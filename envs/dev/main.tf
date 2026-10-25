data "aws_caller_identity" "current" {}

# Resolves your SSO session to its IAM role ARN.
data "aws_iam_session_context" "me" {
  arn = data.aws_caller_identity.current.arn
}

module "storage" {
  source      = "../../modules/storage"
  name_prefix = "artifact-portal-dev"

  # Whoever runs Terraform (your SSO role) administers the key.
  admin_role_arns = [data.aws_iam_session_context.me.issuer_arn]
}

# No cycle: the web client depends on the distribution, but the distribution
# only needs the pool's domain; config.json (not the distribution) reads the
# client id, and the API authorizer depends on the client, not the distribution.
module "auth" {
  source      = "../../modules/auth"
  name_prefix = "artifact-portal-dev"

  callback_urls = ["http://localhost:3000/callback", "https://${module.cdn.distribution_domain}/callback/"]
  logout_urls   = ["http://localhost:3000/", "https://${module.cdn.distribution_domain}/"]
}

module "api" {
  source      = "../../modules/api"
  name_prefix = "artifact-portal-dev"

  bucket_name = module.storage.bucket_name
  bucket_arn  = module.storage.bucket_arn
  kms_key_arn = module.storage.kms_key_arn

  issuer_url = module.auth.issuer_url
  audiences  = [module.auth.web_client_id, module.auth.ci_client_id]

  # The CloudFront origin is deliberately NOT listed here. CORS lives inline on
  # aws_apigatewayv2_api, and the distribution's /api origin is that same
  # resource's endpoint: api -> distribution -> api would be a cycle. It isn't
  # needed either: the site calls /api/* on its own origin, so the browser
  # never makes a cross-origin request. CORS here only serves local dev.
  cors_origins = ["http://localhost:3000"]
}

module "cdn" {
  source      = "../../modules/cdn"
  name_prefix = "artifact-portal-dev"

  api_endpoint   = module.api.api_url
  cognito_domain = module.auth.hosted_login_domain
  web_client_id  = module.auth.web_client_id
}
