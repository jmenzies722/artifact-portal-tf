# Rotation runs once every 30 days, so a single error is the whole signal:
# no 2-of-3 smoothing like the API Lambdas. A failed rotation is safe
# (AWSCURRENT is untouched, CI keeps working) but must not be silent.
resource "aws_cloudwatch_metric_alarm" "rotation_failed" {
  alarm_name          = "${var.name_prefix}-ci-secret-rotation-failed"
  alarm_description   = "CI secret rotation (${var.rotation_function_name}) raised an error. CI still works on AWSCURRENT. Runbook: modules/auth/ROTATION.md; check /aws/lambda/${var.rotation_function_name}, clear any stuck AWSPENDING stage, then rotate again."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = var.rotation_function_name }
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
