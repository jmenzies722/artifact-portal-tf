output "user_pool_id" {
  value = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.this.arn
}

output "issuer_url" {
  value = "https://${aws_cognito_user_pool.this.endpoint}"
}

output "web_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "ci_client_id" {
  value = aws_cognito_user_pool_client.ci.id
}

output "hosted_login_domain" {
  value = "https://${aws_cognito_user_pool_domain.this.domain}.auth.${split("_", aws_cognito_user_pool.this.id)[0]}.amazoncognito.com"
}

output "ci_secret_arn" {
  value = aws_secretsmanager_secret.ci.arn
}
