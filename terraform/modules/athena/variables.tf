variable "name" {
  description = "Workgroup name."
  type        = string
}

variable "results_bucket_name" {
  description = "Bucket for query results."
  type        = string
}

variable "results_prefix" {
  description = "Key prefix for query results, with trailing slash."
  type        = string
  default     = "athena/"
}

variable "kms_key_arn" {
  description = "KMS key used to encrypt query results."
  type        = string
}

variable "bytes_scanned_cutoff_per_query" {
  description = "Per-query scan limit in bytes (Athena minimum is 10 MB)."
  type        = number
  default     = 10737418240 # 10 GiB

  validation {
    condition     = var.bytes_scanned_cutoff_per_query >= 10485760
    error_message = "Athena requires a cutoff of at least 10485760 bytes (10 MB)."
  }
}

variable "force_destroy" {
  description = "Delete saved queries with the workgroup on destroy."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags applied to the workgroup."
  type        = map(string)
  default     = {}
}
