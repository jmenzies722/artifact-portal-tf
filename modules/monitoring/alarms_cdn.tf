# CloudFront publishes its metrics only in us-east-1. That is already this
# stack's region, so no provider alias is needed; deploying elsewhere would
# need one for this alarm.
# Gated like the API alarms: with 2 requests, one error is a "50% error rate".
resource "aws_cloudwatch_metric_alarm" "cloudfront_5xx" {
  alarm_name          = "${var.name_prefix}-cloudfront-5xx"
  alarm_description   = "CloudFront 5xx error rate above 5% in 2 of 3 5-minute windows with at least 10 requests. Covers both origins (S3 site and /api). Runbook: if the API alarm is also firing, start there; otherwise check the S3 origin and OAC."
  comparison_operator = "GreaterThanThreshold"
  threshold           = 5
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "gated"
    expression  = "IF(reqs >= 10, rate, 0)"
    label       = "5xx rate (%), gated"
    return_data = true
  }

  metric_query {
    id = "rate"
    metric {
      namespace   = "AWS/CloudFront"
      metric_name = "5xxErrorRate"
      dimensions  = { DistributionId = var.distribution_id, Region = "Global" }
      stat        = "Average"
      period      = 300
    }
  }

  metric_query {
    id = "reqs"
    metric {
      namespace   = "AWS/CloudFront"
      metric_name = "Requests"
      dimensions  = { DistributionId = var.distribution_id, Region = "Global" }
      stat        = "Sum"
      period      = 300
    }
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}
