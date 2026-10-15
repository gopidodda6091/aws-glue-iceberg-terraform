variable "name" {
  description = "Name prefix for the role and policy."
  type        = string
}

variable "account_id" {
  description = "AWS account id."
  type        = string
}

variable "region" {
  description = "AWS region."
  type        = string
}

variable "partition" {
  description = "AWS partition."
  type        = string
  default     = "aws"
}

variable "raw_bucket_arn" {
  description = "ARN of the raw zone bucket."
  type        = string
}

variable "raw_read_prefix" {
  description = "The only raw prefix the job may read, with trailing slash (e.g. shipments/)."
  type        = string

  validation {
    condition     = length(var.raw_read_prefix) > 1 && endswith(var.raw_read_prefix, "/")
    error_message = "raw_read_prefix must be a non-root prefix ending in a slash."
  }
}

variable "curated_bucket_arn" {
  description = "ARN of the curated zone bucket."
  type        = string
}

variable "curated_write_prefix" {
  description = "The only curated prefix the job may write, with trailing slash."
  type        = string

  validation {
    condition     = length(var.curated_write_prefix) > 1 && endswith(var.curated_write_prefix, "/")
    error_message = "curated_write_prefix must be a non-root prefix ending in a slash."
  }
}

variable "artifacts_bucket_arn" {
  description = "ARN of the bucket holding job scripts and temp files."
  type        = string
}

variable "script_key" {
  description = "Exact object key of the job script."
  type        = string
}

variable "temp_prefix" {
  description = "Prefix for the job's temporary files, with trailing slash."
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the lake KMS key."
  type        = string
}

variable "catalog_database_arn" {
  description = "ARN of the Glue catalog database the job may read."
  type        = string
}

variable "catalog_table_arn" {
  description = "ARN of the Iceberg table the job commits to."
  type        = string
}

variable "tags" {
  description = "Tags applied to the role."
  type        = map(string)
  default     = {}
}
