# Least-privilege execution role for the shipments Glue job.
# Every statement names explicit actions and explicit resources; the only
# wildcards are object-key suffixes under a fixed prefix and the CloudWatch
# metrics API, which does not support resource-level permissions.

locals {
  glue_catalog_arn = "arn:${var.partition}:glue:${var.region}:${var.account_id}:catalog"
  log_group_arns = [
    for g in ["/aws-glue/jobs/output", "/aws-glue/jobs/error", "/aws-glue/jobs/logs-v2"] :
    "arn:${var.partition}:logs:${var.region}:${var.account_id}:log-group:${g}:*"
  ]
}

data "aws_iam_policy_document" "assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.account_id]
    }
  }
}

resource "aws_iam_role" "glue_job" {
  name                 = "${var.name}-glue-job"
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  max_session_duration = 3600
  tags                 = var.tags
}

data "aws_iam_policy_document" "glue_job" {
  # --- raw zone: read-only, one prefix --------------------------------------
  statement {
    sid       = "ListRawPrefix"
    actions   = ["s3:ListBucket"]
    resources = [var.raw_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = [var.raw_read_prefix, "${var.raw_read_prefix}*"]
    }
  }

  statement {
    sid       = "ReadRawPrefix"
    actions   = ["s3:GetObject"]
    resources = ["${var.raw_bucket_arn}/${var.raw_read_prefix}*"]
  }

  # --- curated zone: read/write, one prefix (Iceberg data + metadata) ------
  statement {
    sid       = "ListCuratedPrefix"
    actions   = ["s3:ListBucket"]
    resources = [var.curated_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = [var.curated_write_prefix, "${var.curated_write_prefix}*"]
    }
  }

  statement {
    sid       = "ReadWriteCuratedPrefix"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
    resources = ["${var.curated_bucket_arn}/${var.curated_write_prefix}*"]
  }

  # --- artifacts: the one script object, plus the job's temp prefix --------
  statement {
    sid       = "ReadJobScript"
    actions   = ["s3:GetObject"]
    resources = ["${var.artifacts_bucket_arn}/${var.script_key}"]
  }

  statement {
    sid       = "ReadWriteJobTemp"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.artifacts_bucket_arn}/${var.temp_prefix}*"]
  }

  # --- the one KMS key -------------------------------------------------------
  statement {
    sid       = "UseLakeKey"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = [var.kms_key_arn]
  }

  # --- the one catalog database and table ------------------------------------
  statement {
    sid     = "ReadCatalogDatabase"
    actions = ["glue:GetDatabase"]
    resources = [
      local.glue_catalog_arn,
      var.catalog_database_arn,
    ]
  }

  statement {
    sid     = "CommitIcebergTable"
    actions = ["glue:GetTable", "glue:UpdateTable"]
    resources = [
      local.glue_catalog_arn,
      var.catalog_database_arn,
      var.catalog_table_arn,
    ]
  }

  # --- logging and metrics ---------------------------------------------------
  statement {
    sid       = "WriteJobLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = local.log_group_arns
  }

  statement {
    sid       = "PublishGlueMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["Glue"]
    }
  }
}

resource "aws_iam_role_policy" "glue_job" {
  name   = "${var.name}-glue-job"
  role   = aws_iam_role.glue_job.id
  policy = data.aws_iam_policy_document.glue_job.json
}
