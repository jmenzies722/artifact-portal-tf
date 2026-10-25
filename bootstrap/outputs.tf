output "state_bucket" {
  description = "Use this as the backend bucket in envs/*"
  value       = aws_s3_bucket.state.bucket
}

output "gha_plan_role_arn" {
  value = aws_iam_role.gha_plan.arn
}

output "gha_apply_role_arn" {
  value = aws_iam_role.gha_apply.arn
}
