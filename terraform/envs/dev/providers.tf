terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  # State is local for the demo and for CI. For a real account, add an S3
  # backend here (see docs/deploy.md).
}

# One provider block for both targets. When var.use_localstack is true the
# settings in localstack.tf redirect every service endpoint to LocalStack and
# skip the checks LocalStack cannot answer.
provider "aws" {
  region = var.region

  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  s3_use_path_style           = var.use_localstack

  dynamic "endpoints" {
    for_each = var.use_localstack ? [local.localstack_endpoints] : []
    content {
      athena = endpoints.value.athena
      glue   = endpoints.value.glue
      iam    = endpoints.value.iam
      kms    = endpoints.value.kms
      s3     = endpoints.value.s3
      sts    = endpoints.value.sts
    }
  }

  default_tags {
    tags = local.tags
  }
}
