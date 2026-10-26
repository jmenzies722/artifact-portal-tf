resource "aws_cloudwatch_log_group" "fn" {
  for_each          = local.functions
  name              = "/aws/lambda/${local.function_names[each.key]}"
  retention_in_days = 14
}

resource "aws_lambda_function" "fn" {
  for_each         = local.functions
  function_name    = local.function_names[each.key]
  role             = aws_iam_role.fn[each.key].arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "handler.handler"
  memory_size      = 128
  timeout          = 10
  filename         = data.archive_file.fn[each.key].output_path
  source_code_hash = data.archive_file.fn[each.key].output_base64sha256

  environment {
    variables = {
      BUCKET_NAME = var.bucket_name
      KMS_KEY_ARN = var.kms_key_arn
      AUDIT_TABLE = aws_dynamodb_table.audit.name
    }
  }

  tracing_config {
    mode = "Active"
  }

  # Log group and permissions must exist before the first invocation.
  depends_on = [aws_cloudwatch_log_group.fn, aws_iam_role_policy.fn]
}
