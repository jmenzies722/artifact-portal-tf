# No kms_master_key_id on purpose. The AWS-managed aws/sns key's policy can't
# be edited to let cloudwatch.amazonaws.com use it, so alarms would fail to
# publish without any error. Encrypting would take a customer-managed key, and
# alarm messages (names, metric values) aren't worth one here.
resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-alerts"
  tags = local.tags
}

# Only CloudWatch alarms from this account, named for this stack, may publish
# (confused-deputy guard). Same-account IAM principals still get access from
# their own IAM policies.
data "aws_iam_policy_document" "alerts" {
  statement {
    sid       = "CloudWatchAlarmsPublish"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:cloudwatch:${local.region}:${local.account_id}:alarm:${var.name_prefix}-*"]
    }
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.alerts.json
}

# Email subscriptions stay "pending" until the link in AWS's email is clicked;
# Terraform can't confirm them.
resource "aws_sns_topic_subscription" "email" {
  count     = nonsensitive(var.alert_email != "") ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
