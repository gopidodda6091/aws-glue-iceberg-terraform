variable "database_name" {
  description = "Glue Data Catalog database name (lowercase, underscores)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,254}$", var.database_name))
    error_message = "database_name must be lowercase letters, digits and underscores."
  }
}

variable "description" {
  description = "Database description."
  type        = string
  default     = "Curated zone"
}

variable "table_name" {
  description = "Name of the Iceberg table."
  type        = string
}

variable "curated_bucket_name" {
  description = "Bucket that holds the Iceberg data and metadata files."
  type        = string
}

variable "table_prefix" {
  description = "Key prefix of the table inside the curated bucket, without leading slash, with trailing slash."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9_/-]+/$", var.table_prefix))
    error_message = "table_prefix must end with a slash and contain no leading slash."
  }
}

variable "columns" {
  description = "Table columns using Glue/Hive type names."
  type = list(object({
    name    = string
    type    = string
    comment = optional(string, "")
  }))
}
