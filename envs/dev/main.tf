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

module "auth" {
  source      = "../../modules/auth"
  name_prefix = "artifact-portal-dev"
}

module "api" {
  source      = "../../modules/api"
  name_prefix = "artifact-portal-dev"

  bucket_name = module.storage.bucket_name
  bucket_arn  = module.storage.bucket_arn
  kms_key_arn = module.storage.kms_key_arn

  issuer_url = module.auth.issuer_url
  audiences  = [module.auth.web_client_id, module.auth.ci_client_id]
}
