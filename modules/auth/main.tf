data "aws_caller_identity" "current" {}

resource "aws_cognito_user_pool" "this" {
  name                     = "${var.name_prefix}-users"
  deletion_protection      = "INACTIVE" # lab: allow destroy
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

  # Only admins create users: partners are invited, never self sign-up.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

resource "aws_cognito_user_group" "this" {
  for_each     = var.groups
  name         = each.key
  description  = each.value
  user_pool_id = aws_cognito_user_pool.this.id
}

# Hosted login page domain (must be globally unique).
resource "aws_cognito_user_pool_domain" "this" {
  domain       = "${var.name_prefix}-${data.aws_caller_identity.current.account_id}"
  user_pool_id = aws_cognito_user_pool.this.id
}
