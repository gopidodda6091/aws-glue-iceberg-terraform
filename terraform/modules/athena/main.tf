# Athena workgroup whose settings override the client: results are always
# written SSE-KMS with the lake key, and any query scanning more than the
# cutoff is cancelled.

resource "aws_athena_workgroup" "this" {
  name          = var.name
  description   = "Analyst workgroup for the curated zone"
  state         = "ENABLED"
  force_destroy = var.force_destroy

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.bytes_scanned_cutoff_per_query

    engine_version {
      selected_engine_version = "Athena engine version 3"
    }

    result_configuration {
      output_location = "s3://${var.results_bucket_name}/${var.results_prefix}"

      encryption_configuration {
        encryption_option = "SSE_KMS"
        kms_key_arn       = var.kms_key_arn
      }
    }
  }

  tags = var.tags
}
