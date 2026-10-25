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
