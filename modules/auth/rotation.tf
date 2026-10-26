# Rotates the CI client secret every 30 days with zero downtime: Cognito keeps
# two secrets per client, so the old one stays valid until the next rotation.
# Design and failure modes: ROTATION.md.

locals {
  rotate_name = "${var.name_prefix}-rotate-ci-secret"
  # Same host as the hosted_login_domain output; the region is the pool id's prefix.
  token_url = "https://${aws_cognito_user_pool_domain.this.domain}.auth.${split("_", aws_cognito_user_pool.this.id)[0]}.amazoncognito.com/oauth2/token"
}

# Single file, no shared/ code: built from contents like the api module, no build step.
data "archive_file" "rotate" {
  type        = "zip"
  output_path = "${path.module}/.build/rotate_ci_secret.zip"

  source {
    content  = file("${path.module}/../../lambda/rotate_ci_secret/handler.py")
    filename = "handler.py"
  }
}

resource "aws_cloudwatch_log_group" "rotate" {
  name              = "/aws/lambda/${local.rotate_name}"
  retention_in_days = 14
}

data "aws_iam_policy_document" "rotate_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "rotate" {
  name               = local.rotate_name # artifact-portal-dev-*: the only IAM the CI apply role may manage
  assume_role_policy = data.aws_iam_policy_document.rotate_assume.json
}

data "aws_iam_policy_document" "rotate" {
  statement {
    sid       = "OwnLogGroup"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.rotate.arn}:*"]
  }

  # This one secret only. Default aws/secretsmanager key, so no KMS grant needed.
  statement {
    sid = "RotateThisSecret"
    actions = [
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecretVersionStage",
    ]
    resources = [aws_secretsmanager_secret.ci.arn]
  }

  # Cognito's IAM resource is the pool, so this can't narrow to the CI client;
  # the handler only ever passes CLIENT_ID.
  statement {
    sid = "ManageClientSecrets"
    actions = [
      "cognito-idp:AddUserPoolClientSecret",
      "cognito-idp:ListUserPoolClientSecrets",
      "cognito-idp:DeleteUserPoolClientSecret",
    ]
    resources = [aws_cognito_user_pool.this.arn]
  }
}

resource "aws_iam_role_policy" "rotate" {
  name   = "least-privilege"
  role   = aws_iam_role.rotate.id
  policy = data.aws_iam_policy_document.rotate.json
}

resource "aws_lambda_function" "rotate" {
  function_name    = local.rotate_name
  role             = aws_iam_role.rotate.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "handler.handler"
  memory_size      = 128
  timeout          = 30 # testSecret may retry the token endpoint a few times
  filename         = data.archive_file.rotate.output_path
  source_code_hash = data.archive_file.rotate.output_base64sha256

  environment {
    variables = {
      USER_POOL_ID = aws_cognito_user_pool.this.id
      CLIENT_ID    = aws_cognito_user_pool_client.ci.id
      TOKEN_URL    = local.token_url
      SCOPE        = "artifacts/write"
    }
  }

  depends_on = [aws_cloudwatch_log_group.rotate, aws_iam_role_policy.rotate]
}

# Only Secrets Manager, and only for this secret, may invoke the rotator.
resource "aws_lambda_permission" "rotate" {
  statement_id  = "AllowSecretsManager"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rotate.function_name
  principal     = "secretsmanager.amazonaws.com"
  source_arn    = aws_secretsmanager_secret.ci.arn
}

resource "aws_secretsmanager_secret_rotation" "ci" {
  secret_id           = aws_secretsmanager_secret.ci.id
  rotation_lambda_arn = aws_lambda_function.rotate.arn

  # Don't rotate as a side effect of the apply that creates this: run the
  # first rotation by hand and watch it (ROTATION.md, "First rotation").
  rotate_immediately = false

  rotation_rules {
    automatically_after_days = 30
  }

  depends_on = [aws_lambda_permission.rotate, aws_secretsmanager_secret_version.ci]
}
