locals {
  # Least privilege: each function gets only the data actions it uses.
  data_statements = {
    list_files = [
      { actions = ["s3:ListBucket"], resources = [var.bucket_arn] },
    ]
    upload_url = [
      { actions = ["s3:PutObject"], resources = ["${var.bucket_arn}/*"] },
      { actions = ["kms:GenerateDataKey", "kms:Encrypt"], resources = [var.kms_key_arn] },
    ]
    download_url = [
      { actions = ["s3:GetObject"], resources = ["${var.bucket_arn}/*"] },
      { actions = ["kms:Decrypt"], resources = [var.kms_key_arn] },
    ]
    delete_file = [
      { actions = ["s3:DeleteObject"], resources = ["${var.bucket_arn}/*"] },
    ]
  }
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "fn" {
  for_each           = local.functions
  name               = local.function_names[each.key]
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "fn" {
  for_each = local.functions

  statement {
    sid       = "OwnLogGroup"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.fn[each.key].arn}:*"]
  }

  statement {
    sid       = "XRay"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"] # X-Ray has no resource-level permissions
  }

  dynamic "statement" {
    for_each = local.data_statements[each.key]
    content {
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

resource "aws_iam_role_policy" "fn" {
  for_each = local.functions
  name     = "least-privilege"
  role     = aws_iam_role.fn[each.key].id
  policy   = data.aws_iam_policy_document.fn[each.key].json
}
