output "bucket_name" {
  value = aws_s3_bucket.artifacts.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.artifacts.arn
}

output "kms_key_arn" {
  value = aws_kms_key.artifacts.arn
}

output "kms_alias" {
  value = aws_kms_alias.artifacts.name
}
