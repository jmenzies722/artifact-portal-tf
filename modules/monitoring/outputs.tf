output "sns_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "dashboard_url" {
  value = "https://${local.region}.console.aws.amazon.com/cloudwatch/home?region=${local.region}#dashboards/dashboard/${aws_cloudwatch_dashboard.slo.dashboard_name}"
}

output "alarm_names" {
  value = concat(
    [
      aws_cloudwatch_metric_alarm.api_availability.alarm_name,
      aws_cloudwatch_metric_alarm.api_latency_p95.alarm_name,
      aws_cloudwatch_metric_alarm.cloudfront_5xx.alarm_name,
    ],
    [for a in aws_cloudwatch_metric_alarm.lambda_errors : a.alarm_name],
    [for a in aws_cloudwatch_metric_alarm.lambda_throttles : a.alarm_name],
  )
}
