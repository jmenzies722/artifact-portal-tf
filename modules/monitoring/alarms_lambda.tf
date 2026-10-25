# One alarm per function so the notification names the broken one.
# Errors are unhandled exceptions/timeouts, not 4xx the handler returns.
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = var.function_names

  alarm_name          = "${var.name_prefix}-lambda-errors-${each.key}"
  alarm_description   = "Lambda ${each.value} raised errors in 2 of 3 5-minute windows. Runbook: check /aws/lambda/${each.value} for the stack trace and X-Ray for the failing call."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = each.value }
  statistic           = "Sum"
  period              = 300
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}

# Any throttle is worth knowing about at once: it means the account
# concurrency limit or the stage's rate limit was hit.
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  for_each = var.function_names

  alarm_name          = "${var.name_prefix}-lambda-throttles-${each.key}"
  alarm_description   = "Lambda ${each.value} was throttled. Runbook: check ConcurrentExecutions against the account limit and whether a client is looping."
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  dimensions          = { FunctionName = each.value }
  statistic           = "Sum"
  period              = 300
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}
