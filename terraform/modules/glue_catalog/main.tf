# Catalog database for the curated zone plus the Iceberg table the Glue job
# merges into. Terraform creates the table metadata (format v2); the job only
# commits new snapshots.

resource "aws_glue_catalog_database" "this" {
  name         = var.database_name
  description  = var.description
  location_uri = "s3://${var.curated_bucket_name}/${var.table_prefix}"
}

resource "aws_glue_catalog_table" "iceberg" {
  name          = var.table_name
  database_name = aws_glue_catalog_database.this.name
  table_type    = "EXTERNAL_TABLE"

  open_table_format_input {
    iceberg_input {
      metadata_operation = "CREATE"
      version            = "2"
    }
  }

  storage_descriptor {
    location = "s3://${var.curated_bucket_name}/${var.table_prefix}"

    dynamic "columns" {
      for_each = var.columns
      content {
        name    = columns.value.name
        type    = columns.value.type
        comment = columns.value.comment
      }
    }
  }
}
