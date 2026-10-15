variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Short project name used in resource names."
  type        = string
  default     = "gulf-freight"
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "dev"
}

variable "athena_bytes_scanned_cutoff" {
  description = "Per-query Athena scan limit in bytes."
  type        = number
  default     = 1073741824 # 1 GiB for dev
}

variable "glue_lookback_hours" {
  description = "Hours re-read before the watermark to catch late events."
  type        = number
  default     = 6
}

variable "force_destroy_buckets" {
  description = "Allow destroying non-empty buckets (sandbox accounts only)."
  type        = bool
  default     = false
}
