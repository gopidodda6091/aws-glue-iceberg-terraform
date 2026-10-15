# Uploads the job script (SSE-KMS, as the bucket policy demands), creates a
# Glue security configuration that encrypts job output with the lake key, and
# defines the incremental shipments job with the Iceberg catalog wired in.

locals {
  iceberg_conf = {
    "spark.sql.extensions"                        = "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
    "spark.sql.catalog.glue_catalog"              = "org.apache.iceberg.spark.SparkCatalog"
    "spark.sql.catalog.glue_catalog.warehouse"    = var.warehouse_uri
    "spark.sql.catalog.glue_catalog.catalog-impl" = "org.apache.iceberg.aws.glue.GlueCatalog"
    "spark.sql.catalog.glue_catalog.io-impl"      = "org.apache.iceberg.aws.s3.S3FileIO"
    "spark.sql.catalog.glue_catalog.s3.sse.type"  = "kms"
    "spark.sql.catalog.glue_catalog.s3.sse.key"   = var.kms_key_arn
  }

  # Glue accepts a single --conf argument, so additional settings are chained
  # inside its value: "k1=v1 --conf k2=v2 ...".
  conf_pairs  = [for k in sort(keys(local.iceberg_conf)) : "${k}=${local.iceberg_conf[k]}"]
  conf_string = join(" --conf ", local.conf_pairs)
}

resource "aws_s3_object" "script" {
  bucket                 = var.artifacts_bucket_name
  key                    = var.script_key
  source                 = var.script_source_path
  source_hash            = filemd5(var.script_source_path)
  server_side_encryption = "aws:kms"
  kms_key_id             = var.kms_key_arn
  content_type           = "text/x-python"
}

resource "aws_glue_security_configuration" "this" {
  name = "${var.job_name}-sec"

  encryption_configuration {
    s3_encryption {
      s3_encryption_mode = "SSE-KMS"
      kms_key_arn        = var.kms_key_arn
    }

    cloudwatch_encryption {
      cloudwatch_encryption_mode = "DISABLED"
    }

    job_bookmarks_encryption {
      job_bookmarks_encryption_mode = "DISABLED"
    }
  }
}

resource "aws_glue_job" "this" {
  name                   = var.job_name
  description            = "Incremental load of shipment events into Iceberg (watermark + MERGE INTO)."
  role_arn               = var.role_arn
  glue_version           = var.glue_version
  worker_type            = var.worker_type
  number_of_workers      = var.number_of_workers
  timeout                = var.timeout_minutes
  max_retries            = 0
  security_configuration = aws_glue_security_configuration.this.name

  command {
    name            = "glueetl"
    script_location = "s3://${var.artifacts_bucket_name}/${aws_s3_object.script.key}"
    python_version  = "3"
  }

  execution_property {
    max_concurrent_runs = 1
  }

  default_arguments = merge(
    {
      "--job-language"                     = "python"
      "--datalake-formats"                 = "iceberg"
      "--conf"                             = local.conf_string
      "--TempDir"                          = "s3://${var.artifacts_bucket_name}/${var.temp_prefix}"
      "--enable-metrics"                   = "true"
      "--enable-continuous-cloudwatch-log" = "true"
      "--job-bookmark-option"              = "job-bookmark-disable"
      "--raw_path"                         = var.raw_path
      "--target_table"                     = var.target_table
      "--lookback_hours"                   = tostring(var.lookback_hours)
    },
    var.extra_arguments,
  )

  tags = var.tags
}
