# CI pipeline: client credentials, scoped to artifacts/write only.
resource "aws_cognito_user_pool_client" "ci" {
  name                                 = "${var.name_prefix}-ci"
  user_pool_id                         = aws_cognito_user_pool.this.id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["artifacts/write"]
  supported_identity_providers         = ["COGNITO"]
  access_token_validity                = 1
  token_validity_units {
    access_token = "hours"
  }
  depends_on = [aws_cognito_resource_server.artifacts]
}

# The CI client secret lives in Secrets Manager, never in code. rotation.tf
# rotates it every 30 days, adding and removing Cognito secrets outside
# Terraform. The client itself needs no ignore_changes: rotation edits no
# configurable attribute, and client_secret is read-only here.
resource "aws_secretsmanager_secret" "ci" {
  name                    = "${var.name_prefix}/ci-client"
  description             = "Cognito client credentials for CI uploads"
  recovery_window_in_days = 0 # lab: delete immediately on destroy
}

resource "aws_secretsmanager_secret_version" "ci" {
  secret_id = aws_secretsmanager_secret.ci.id
  secret_string = jsonencode({
    client_id     = aws_cognito_user_pool_client.ci.id
    client_secret = aws_cognito_user_pool_client.ci.client_secret
  })

  # Seed value only. After the first rotation, AWSCURRENT is owned by the
  # rotation Lambda; without this, Terraform would write back the client's
  # first secret, which rotation eventually deletes, and break CI.
  lifecycle {
    ignore_changes = [secret_string]
  }
}
