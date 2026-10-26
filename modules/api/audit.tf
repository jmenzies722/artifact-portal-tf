# Audit trail: one item per allowed upload/download/delete.
# pk = DAY#YYYY-MM-DD keeps "recent activity" a single-partition Query per day;
# sk = <ISO8601 ts>#<request id> sorts by time and stays unique per request.
resource "aws_dynamodb_table" "audit" {
  name         = "${var.name_prefix}-audit"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  # Lab: lets `terraform destroy` succeed. A real audit log would set this true.
  deletion_protection_enabled = false

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "key"
    type = "S"
  }

  # An artifact's full history, newest last: Query key = "<object key>".
  global_secondary_index {
    name            = "by_key"
    hash_key        = "key"
    range_key       = "sk"
    projection_type = "ALL"
  }

  # Same customer-managed key as the artifacts: one key to audit and revoke.
  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  # Items carry expires_at (epoch seconds, +90 days); DynamoDB deletes them for free.
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}
