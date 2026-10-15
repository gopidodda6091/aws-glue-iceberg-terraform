variable "name" {
  description = "Name used for the key description and alias (alias/<name>)."
  type        = string
}

variable "account_id" {
  description = "AWS account id that owns the key."
  type        = string
}

variable "region" {
  description = "Region the key lives in; used to scope kms:ViaService."
  type        = string
}

variable "partition" {
  description = "AWS partition (aws, aws-us-gov, aws-cn)."
  type        = string
  default     = "aws"
}

variable "rotation_period_in_days" {
  description = "Automatic rotation period. AWS allows 90-2560 days."
  type        = number
  default     = 365

  validation {
    condition     = var.rotation_period_in_days >= 90 && var.rotation_period_in_days <= 2560
    error_message = "rotation_period_in_days must be between 90 and 2560."
  }
}

variable "deletion_window_in_days" {
  description = "Waiting period before a scheduled key deletion completes."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags applied to the key."
  type        = map(string)
  default     = {}
}
