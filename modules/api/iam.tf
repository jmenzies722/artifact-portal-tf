data "aws_region" "current" {}

locals {
  # The audit table is encrypted with the artifacts key; these grants only
  # work when DynamoDB is the caller, not for direct kms:Decrypt calls.
  via_dynamodb = [{ test = "StringEquals", variable = "kms:ViaService", values = ["dynamodb.${data.aws_region.current.region}.amazonaws.com"] }]

  # Writers can append audit items but never read, change or delete them.
  audit_write = [
    { actions = ["dynamodb:PutItem"], resources = [aws_dynamodb_table.audit.arn] },
    { actions = ["kms:GenerateDataKey", "kms:Decrypt"], resources = [var.kms_key_arn], conditions = local.via_dynamodb },
  ]

  # Least privilege: each function gets only the data actions it uses.
  data_statements = {
    list_files = [
      { actions = ["s3:ListBucket"], resources = [var.bucket_arn] },
    ]
    upload_url = concat([
      { actions = ["s3:PutObject"], resources = ["${var.bucket_arn}/*"] },
      { actions = ["kms:GenerateDataKey", "kms:Encrypt"], resources = [var.kms_key_arn] },
    ], local.audit_write)
    download_url = concat([
      { actions = ["s3:GetObject"], resources = ["${var.bucket_arn}/*"] },
      { actions = ["kms:Decrypt"], resources = [var.kms_key_arn] },
    ], local.audit_write)
    delete_file = concat([
      { actions = ["s3:DeleteObject"], resources = ["${var.bucket_arn}/*"] },
    ], local.audit_write)
    # Base table only: the by_key index isn't served by the API.
    activity = [
      { actions = ["dynamodb:Query"], resources = [aws_dynamodb_table.audit.arn] },
      { actions = ["kms:Decrypt"], resources = [var.kms_key_arn], conditions = local.via_dynamodb },
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

      dynamic "condition" {
        for_each = lookup(statement.value, "conditions", [])
        content {
          test     = condition.value.test
          variable = condition.value.variable
          values   = condition.value.values
        }
      }
    }
  }
}

resource "aws_iam_role_policy" "fn" {
  for_each = local.functions
  name     = "least-privilege"
  role     = aws_iam_role.fn[each.key].id
  policy   = data.aws_iam_policy_document.fn[each.key].json
}
