# One customer-managed key for every encrypted surface of the lake:
# S3 zones, Glue job output and Athena query results.

data "aws_iam_policy_document" "key" {
  # Standard account-root statement: lets IAM policies in this account grant
  # use of the key. Without it, only the key policy could grant access.
  statement {
    sid       = "EnableAccountIamDelegation"
    effect    = "Allow"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:${var.partition}:iam::${var.account_id}:root"]
    }
  }

  # Refuse any use of the key that does not come through S3, Glue or Athena
  # in this region, for principals other than the account root.
  statement {
    sid       = "DenyUseOutsideDataServices"
    effect    = "Deny"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey*", "kms:ReEncrypt*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    condition {
      test     = "StringNotEquals"
      variable = "kms:ViaService"
      values = [
        "s3.${var.region}.amazonaws.com",
        "glue.${var.region}.amazonaws.com",
        "athena.${var.region}.amazonaws.com",
      ]
    }

    condition {
      test     = "StringNotEquals"
      variable = "aws:PrincipalArn"
      values   = ["arn:${var.partition}:iam::${var.account_id}:root"]
    }
  }
}

resource "aws_kms_key" "this" {
  description             = "${var.name} data lake key"
  enable_key_rotation     = true
  rotation_period_in_days = var.rotation_period_in_days
  deletion_window_in_days = var.deletion_window_in_days
  policy                  = data.aws_iam_policy_document.key.json
  tags                    = var.tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.name}"
  target_key_id = aws_kms_key.this.key_id
}
