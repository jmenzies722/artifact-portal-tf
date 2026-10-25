data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  root_arn   = "arn:${data.aws_partition.current.partition}:iam::${local.account_id}:root"
}

# ---------- Customer-managed KMS key ----------
data "aws_iam_policy_document" "kms" {
  # Account root keeps access so the key can never be orphaned.
  statement {
    sid       = "EnableRootAccess"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = [local.root_arn]
    }
  }

  # Named admins can manage the key but this statement grants no data access.
  statement {
    sid = "KeyAdministrators"
    actions = [
      "kms:Create*", "kms:Describe*", "kms:Enable*", "kms:List*", "kms:Put*",
      "kms:Update*", "kms:Revoke*", "kms:Disable*", "kms:Get*", "kms:Delete*",
      "kms:TagResource", "kms:UntagResource", "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion", "kms:RotateKeyOnDemand",
    ]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = var.admin_role_arns
    }
  }

  # S3 may use the key, but only for requests to this account's S3.
  statement {
    sid       = "AllowS3UseInThisAccount"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:DescribeKey"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["s3.${data.aws_region.current.region}.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "kms:CallerAccount"
      values   = [local.account_id]
    }
  }
}

data "aws_region" "current" {}

resource "aws_kms_key" "artifacts" {
  description             = "${var.name_prefix} artifacts encryption key"
  enable_key_rotation     = true
  rotation_period_in_days = 365
  deletion_window_in_days = 7
  policy                  = data.aws_iam_policy_document.kms.json
}

resource "aws_kms_alias" "artifacts" {
  name          = "alias/${var.name_prefix}-artifacts"
  target_key_id = aws_kms_key.artifacts.key_id
}

# ---------- Artifacts bucket ----------
resource "aws_s3_bucket" "artifacts" {
  bucket        = "${var.name_prefix}-artifacts-${local.account_id}"
  force_destroy = true # lab only: lets terraform destroy empty it
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.artifacts.arn
    }
    bucket_key_enabled = true # cuts KMS request costs
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

