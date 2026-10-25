output "artifacts_bucket" {
  value = module.storage.bucket_name
}

output "kms_alias" {
  value = module.storage.kms_alias
}

output "user_pool_id" {
  value = module.auth.user_pool_id
}

output "web_client_id" {
  value = module.auth.web_client_id
}

output "hosted_login_domain" {
  value = module.auth.hosted_login_domain
}

output "ci_secret_arn" {
  value = module.auth.ci_secret_arn
}
