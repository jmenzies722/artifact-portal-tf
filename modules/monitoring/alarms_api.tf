# ---------- API availability: share of requests that are not 5xx ----------
# 4xx are deliberately excluded: RBAC denials are 403s by design and bad
# client input is 400. Neither means the service is down, so neither may
# spend the error budget.
resource "aws_cloudwatch_metric_alarm" "api_availability" {
  alarm_name          = "${var.name_prefix}-api-availability"
  alarm_description   = "API 5xx rate above ${local.error_budget_txt}% (SLO ${var.availability_target}% non-5xx) in 2 of 3 5-minute windows with >= ${local.min_requests} requests. 4xx are excluded. Runbook: query ${local.api_logs} for status >= 500, then the failing route's /aws/lambda/<fn> logs."
  comparison_operator = "GreaterThanThreshold"
  threshold           = local.error_budget_pct
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    label       = "5xx rate (%)"
    expression  = "IF(mcount >= ${local.min_requests}, 100 * m5xx / mcount, 0)"
    return_data = true
  }

  metric_query {
    id = "m5xx"
    metric {
      namespace   = "AWS/ApiGateway"
      metric_name = "5xx"
      dimensions  = local.api_dims
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id = "mcount"
    metric {
      namespace   = "AWS/ApiGateway"
      metric_name = "Count"
      dimensions  = local.api_dims
      period      = 300
      stat        = "Sum"
    }
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}

# ---------- API latency: p95 end-to-end ----------
# 3 of 3 so a single cold start can't page.
resource "aws_cloudwatch_metric_alarm" "api_latency_p95" {
  alarm_name          = "${var.name_prefix}-api-latency-p95"
  alarm_description   = "API p95 latency above ${var.latency_p95_ms} ms for 3 consecutive 5-minute windows. Runbook: compare Latency with IntegrationLatency on the dashboard (gateway vs Lambda), then check Lambda Duration and X-Ray traces."
  namespace           = "AWS/ApiGateway"
  metric_name         = "Latency"
  dimensions          = local.api_dims
  extended_statistic  = "p95"
  period              = 300
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.latency_p95_ms
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  tags          = local.tags
}
