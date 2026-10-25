# ---------- GitHub Actions -> AWS with OIDC (no stored access keys) ----------
# Lives in bootstrap because a pipeline can't create the role it logs in with.

locals {
  # GitHub's immutable subject: owner and repo IDs, so a renamed or
  # re-created repo with the same name can't inherit this trust.
  repo         = "jmenzies722@101149635/artifact-portal-tf@1432690557"
  state_bucket = aws_s3_bucket.state.arn
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

# ---------- plan: any pull request, read-only ----------
data "aws_iam_policy_document" "plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Pinned to this repo's PRs. Never a wildcard: that would trust every repo on GitHub.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.repo}:pull_request"]
    }
  }
}

resource "aws_iam_role" "gha_plan" {
  name                 = "artifact-portal-gha-plan"
  assume_role_policy   = data.aws_iam_policy_document.plan_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.gha_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# ReadOnlyAccess can't take the state lock or read secret values that
# Terraform refreshes, so grant exactly those.
data "aws_iam_policy_document" "plan_extra" {
  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [local.state_bucket, "${local.state_bucket}/*"]
  }
  statement {
    sid       = "StateLockFile"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.state_bucket}/*.tflock"]
  }
  statement {
    sid       = "RefreshSecretValues"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:artifact-portal-*"]
  }
}

resource "aws_iam_role_policy" "plan_extra" {
  name   = "state-and-refresh"
  role   = aws_iam_role.gha_plan.id
  policy = data.aws_iam_policy_document.plan_extra.json
}

# ---------- apply: only the approved "production" environment ----------
data "aws_iam_policy_document" "apply_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Jobs using an environment get sub = environment:<name>, not the branch.
    # production requires your approval and only deploys from main.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.repo}:environment:production"]
    }
  }
}

resource "aws_iam_role" "gha_apply" {
  name                 = "artifact-portal-gha-apply"
  assume_role_policy   = data.aws_iam_policy_document.apply_trust.json
  max_session_duration = 3600
}

# PowerUser = everything except IAM/Organizations...
resource "aws_iam_role_policy_attachment" "apply_poweruser" {
  role       = aws_iam_role.gha_apply.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

# ...plus IAM, but only on this project's own roles and policies.
data "aws_iam_policy_document" "apply_iam" {
  statement {
    sid     = "ProjectIamOnly"
    actions = ["iam:*"]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/artifact-portal-dev-*",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/artifact-portal-dev-*",
    ]
  }
  statement {
    sid       = "ReadIam"
    actions   = ["iam:Get*", "iam:List*"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "apply_iam" {
  name   = "project-iam"
  role   = aws_iam_role.gha_apply.id
  policy = data.aws_iam_policy_document.apply_iam.json
}
