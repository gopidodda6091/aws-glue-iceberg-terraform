# LocalStack endpoint override. Used by `make plan-local` and by CI, which run
#   terraform plan -var use_localstack=true
# with AWS_ACCESS_KEY_ID=test / AWS_SECRET_ACCESS_KEY=test (dummy values that
# LocalStack accepts). Nothing here is used when use_localstack is false.

variable "use_localstack" {
  description = "Point the AWS provider at LocalStack instead of real AWS."
  type        = bool
  default     = false
}

variable "localstack_endpoint" {
  description = "Base URL of the LocalStack edge port."
  type        = string
  default     = "http://localhost:4566"
}

locals {
  localstack_endpoints = {
    athena = var.localstack_endpoint
    glue   = var.localstack_endpoint
    iam    = var.localstack_endpoint
    kms    = var.localstack_endpoint
    s3     = var.localstack_endpoint
    sts    = var.localstack_endpoint
  }
}
