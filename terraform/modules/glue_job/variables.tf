variable "job_name" {
  description = "Glue job name."
  type        = string
}

variable "role_arn" {
  description = "Execution role ARN (from the iam module)."
  type        = string
}

variable "artifacts_bucket_name" {
  description = "Bucket holding the script and temp files."
  type        = string
}

variable "script_key" {
  description = "Object key for the uploaded script."
  type        = string
}

variable "script_source_path" {
  description = "Local path to the PySpark script."
  type        = string
}

variable "temp_prefix" {
  description = "Prefix in the artifacts bucket for Glue temp files, with trailing slash."
  type        = string
}

variable "kms_key_arn" {
  description = "Lake KMS key used for the script object, job output and Iceberg files."
  type        = string
}

variable "warehouse_uri" {
  description = "Iceberg warehouse URI, e.g. s3://bucket/shipments/."
  type        = string
}

variable "raw_path" {
  description = "S3 URI the job reads JSON events from."
  type        = string
}

variable "target_table" {
  description = "Fully-qualified Iceberg target, e.g. glue_catalog.curated.shipments."
  type        = string
}

variable "lookback_hours" {
  description = "Hours re-read before the watermark to absorb late-arriving events."
  type        = number
  default     = 6
}

variable "glue_version" {
  description = "Glue runtime version (5.0 = Spark 3.5, Python 3.11)."
  type        = string
  default     = "5.0"
}

variable "worker_type" {
  description = "Glue worker type."
  type        = string
  default     = "G.1X"
}

variable "number_of_workers" {
  description = "Number of workers."
  type        = number
  default     = 2
}

variable "timeout_minutes" {
  description = "Job timeout in minutes."
  type        = number
  default     = 30
}

variable "extra_arguments" {
  description = "Additional job arguments merged over the defaults."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags applied to the job."
  type        = map(string)
  default     = {}
}
