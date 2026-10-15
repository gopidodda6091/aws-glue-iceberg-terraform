output "database_name" {
  description = "Catalog database name."
  value       = aws_glue_catalog_database.this.name
}

output "database_arn" {
  description = "Catalog database ARN."
  value       = aws_glue_catalog_database.this.arn
}

output "table_name" {
  description = "Iceberg table name."
  value       = aws_glue_catalog_table.iceberg.name
}

output "table_arn" {
  description = "Iceberg table ARN."
  value       = aws_glue_catalog_table.iceberg.arn
}
