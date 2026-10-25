output "state_bucket" {
  description = "Use this as the backend bucket in envs/*"
  value       = aws_s3_bucket.state.bucket
}
