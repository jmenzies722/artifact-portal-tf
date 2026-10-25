# Scopes machines can be granted, e.g. artifacts/write.
resource "aws_cognito_resource_server" "artifacts" {
  identifier   = "artifacts"
  name         = "${var.name_prefix}-artifacts-api"
  user_pool_id = aws_cognito_user_pool.this.id

  scope {
    scope_name        = "read"
    scope_description = "List and download artifacts"
  }
  scope {
    scope_name        = "write"
    scope_description = "Upload artifacts"
  }
}

# Browser app: authorization code + PKCE, no secret.
resource "aws_cognito_user_pool_client" "web" {
  name                                 = "${var.name_prefix}-web"
  user_pool_id                         = aws_cognito_user_pool.this.id
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = var.callback_urls
  logout_urls                          = var.logout_urls
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_SRP_AUTH"]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true

  access_token_validity  = 1  # hours
  id_token_validity      = 1  # hours
  refresh_token_validity = 12 # hours
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "hours"
  }
}
