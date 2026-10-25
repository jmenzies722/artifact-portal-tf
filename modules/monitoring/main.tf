data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region

  # Error budget in percent, e.g. 99.9 -> 0.1. Terraform does exact big-float
  # math, so 100 - 99.9 needs rounding before it goes into text.
  error_budget_pct = 100 - var.availability_target
  error_budget_txt = format("%.4g", local.error_budget_pct)

  # Below this many requests per window the error rate counts as 0: at lab
  # volume one 5xx out of 3 requests is 33% and would page for nothing.
  min_requests = 10

  api_dims = {
    ApiId = var.api_id
    Stage = var.api_stage
  }

  # Where to look first; repeated in every alarm description.
  api_logs = "/aws/apigateway/${var.name_prefix}-api"

  tags = {
    Component = "monitoring"
  }
}
