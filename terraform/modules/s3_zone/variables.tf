variable "name_prefix" {
  description = "Prefix for the bucket name, e.g. gulf-freight-dev-123456789012."
  type        = string
}

variable "zone" {
  description = "Lake zone this bucket holds (raw, curated, athena-results, artifacts)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.zone))
    error_message = "zone must be lowercase letters, digits and hyphens."
  }
}

variable "kms_key_arn" {
  description = "ARN of the KMS key every object must be encrypted with."
  type        = string
}

variable "force_destroy" {
  description = "Allow terraform destroy to delete a non-empty bucket. Keep false outside sandboxes."
  type        = bool
  default     = false
}

variable "noncurrent_version_expiration_days" {
  description = "Expire noncurrent object versions after N days; 0 disables the rule."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags applied to the bucket."
  type        = map(string)
  default     = {}
}
