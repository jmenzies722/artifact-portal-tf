# CloudFront publishes its metrics only in us-east-1. That is already this
# stack's region, so no provider alias is needed; deploying elsewhere would
# need one for this alarm.
resource "aws_cloudwatch_metric_alarm" "cloudfront_5xx" {
  alarm_name          = "${var.name_prefix}-cloudfront-5xx"
  alarm_description   = "CloudFront 5xx error rate above 5% in 2 of 3 5-minute windows. Covers both origins (S3 site and /api). Runbook: if the API alarm is also firing, start there; otherwise check the S3 origin and OAC."
  namespace           = "AWS/CloudFront"
  metric_name         = "5xxErrorRate"
  dimensions          = { DistributionId = var.distribution_id, Region = "Global" }
  statistic           = "Average"
  period              = 300
  comparison_operator = "GreaterThanThreshold"
  threshold           = 5
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}
