# ---------- PagerDuty paging ----------
# The integration URL lets anyone who has it page on-call, so it lives in
# Secrets Manager (created by hand, never in git) and only its name is here.
# Raw message delivery stays off: PagerDuty's CloudWatch integration expects
# the standard SNS envelope with the alarm JSON nested in Message. ALARM opens
# an incident, OK resolves it.
variable "pagerduty_secret_name" {
  description = "Secrets Manager secret holding the PagerDuty CloudWatch integration URL; empty disables paging"
  type        = string
  default     = ""
}

data "aws_secretsmanager_secret_version" "pagerduty" {
  count     = var.pagerduty_secret_name != "" ? 1 : 0
  secret_id = var.pagerduty_secret_name
}

resource "aws_sns_topic_subscription" "pagerduty" {
  count                  = var.pagerduty_secret_name != "" ? 1 : 0
  topic_arn              = aws_sns_topic.alerts.arn
  protocol               = "https"
  endpoint               = data.aws_secretsmanager_secret_version.pagerduty[0].secret_string
  endpoint_auto_confirms = true # PagerDuty confirms SNS subscriptions itself
  raw_message_delivery   = false
}
