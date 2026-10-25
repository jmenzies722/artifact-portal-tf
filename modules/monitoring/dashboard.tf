locals {
  dashboard_name = "${var.name_prefix}-slo"

  # Dimensions in the dashboard's flat ["Namespace", "Metric", k, v, ...] form.
  api_d = ["ApiId", var.api_id, "Stage", var.api_stage]
  cdn_d = ["DistributionId", var.distribution_id, "Region", "Global"]

  # Shared by every metric widget.
  widget = { region = local.region, period = 300, view = "timeSeries" }

  all_alarm_arns = concat(
    [
      aws_cloudwatch_metric_alarm.api_availability.arn,
      aws_cloudwatch_metric_alarm.api_latency_p95.arn,
      aws_cloudwatch_metric_alarm.cloudfront_5xx.arn,
    ],
    [for a in aws_cloudwatch_metric_alarm.lambda_errors : a.arn],
    [for a in aws_cloudwatch_metric_alarm.lambda_throttles : a.arn],
  )
}

resource "aws_cloudwatch_dashboard" "slo" {
  dashboard_name = local.dashboard_name

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "text", x = 0, y = 0, width = 24, height = 3
        properties = {
          markdown = join("\n", [
            "## ${var.name_prefix} SLOs",
            "- **Availability:** ${var.availability_target}% of API requests are not 5xx, per 5-minute window. Windows with fewer than ${local.min_requests} requests count as healthy. 4xx (including RBAC 403s) are expected and excluded.",
            "- **Latency:** API p95 under ${var.latency_p95_ms} ms.",
            "Alarms publish to SNS `${aws_sns_topic.alerts.name}`.",
          ])
        }
      },
      {
        type = "metric", x = 0, y = 3, width = 12, height = 6
        properties = merge(local.widget, {
          title = "API requests and errors"
          stat  = "Sum"
          metrics = [
            concat(["AWS/ApiGateway", "Count"], local.api_d, [{ label = "Requests" }]),
            concat(["AWS/ApiGateway", "4xx"], local.api_d, [{ label = "4xx (expected)" }]),
            concat(["AWS/ApiGateway", "5xx"], local.api_d, [{ label = "5xx (SLO)" }]),
          ]
        })
      },
      {
        type = "metric", x = 12, y = 3, width = 12, height = 6
        properties = merge(local.widget, {
          title = "API availability (%)"
          metrics = [
            # Same gate as the alarm, so the graph shows what the alarm sees.
            [{ id = "avail", label = "Availability", expression = "100 - IF(mcount >= ${local.min_requests}, 100 * m5xx / mcount, 0)" }],
            concat(["AWS/ApiGateway", "5xx"], local.api_d, [{ id = "m5xx", stat = "Sum", visible = false }]),
            concat(["AWS/ApiGateway", "Count"], local.api_d, [{ id = "mcount", stat = "Sum", visible = false }]),
          ]
          yAxis       = { left = { max = 100 } }
          annotations = { horizontal = [{ label = "SLO ${var.availability_target}%", value = var.availability_target }] }
        })
      },
      {
        type = "metric", x = 0, y = 9, width = 12, height = 6
        properties = merge(local.widget, {
          title = "API latency (ms)"
          metrics = [
            concat(["AWS/ApiGateway", "Latency"], local.api_d, [{ stat = "p50", label = "p50" }]),
            concat(["AWS/ApiGateway", "Latency"], local.api_d, [{ stat = "p95", label = "p95" }]),
            concat(["AWS/ApiGateway", "IntegrationLatency"], local.api_d, [{ stat = "p95", label = "p95 integration (Lambda)" }]),
          ]
          annotations = { horizontal = [{ label = "SLO p95 ${var.latency_p95_ms} ms", value = var.latency_p95_ms }] }
        })
      },
      {
        type = "alarm", x = 12, y = 9, width = 12, height = 6
        properties = {
          title  = "Alarm status"
          alarms = local.all_alarm_arns
        }
      },
      {
        type = "metric", x = 0, y = 15, width = 12, height = 6
        properties = merge(local.widget, {
          title   = "Lambda errors"
          stat    = "Sum"
          metrics = [for k, fn in var.function_names : ["AWS/Lambda", "Errors", "FunctionName", fn, { label = k }]]
        })
      },
      {
        type = "metric", x = 12, y = 15, width = 12, height = 6
        properties = merge(local.widget, {
          title   = "Lambda duration p95 (ms)"
          stat    = "p95"
          metrics = [for k, fn in var.function_names : ["AWS/Lambda", "Duration", "FunctionName", fn, { label = k }]]
        })
      },
      {
        type = "metric", x = 0, y = 21, width = 24, height = 6
        properties = merge(local.widget, {
          # CloudFront metrics only exist in us-east-1 (see alarms_cdn.tf).
          title = "CloudFront"
          metrics = [
            concat(["AWS/CloudFront", "Requests"], local.cdn_d, [{ stat = "Sum", label = "Requests" }]),
            concat(["AWS/CloudFront", "5xxErrorRate"], local.cdn_d, [{ stat = "Average", label = "5xx rate (%)", yAxis = "right" }]),
          ]
          annotations = { horizontal = [{ label = "Alarm 5%", value = 5, yAxis = "right" }] }
        })
      },
    ]
  })
}
