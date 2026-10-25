output "artifacts_bucket" {
  value = module.storage.bucket_name
}

output "kms_alias" {
  value = module.storage.kms_alias
}
