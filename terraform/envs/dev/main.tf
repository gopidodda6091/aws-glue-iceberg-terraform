data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  partition   = data.aws_partition.current.partition
  name        = "${var.project}-${var.environment}"
  name_prefix = "${local.name}-${local.account_id}"

  # One dataset, one prefix per zone. These are the only paths the job role
  # can touch.
  raw_prefix     = "shipments/"
  curated_prefix = "shipments/"
  script_key     = "glue/scripts/shipments_incremental.py"
  temp_prefix    = "glue/tmp/shipments_incremental/"

  database_name = replace("${var.project}_${var.environment}_curated", "-", "_")
  table_name    = "shipments"

  tags = {
    project     = var.project
    environment = var.environment
    managed-by  = "terraform"
  }

  shipment_columns = [
    { name = "shipment_id", type = "string", comment = "Business key" },
    { name = "event_id", type = "string", comment = "Unique id of the source event" },
    { name = "event_ts", type = "timestamp", comment = "Event time (UTC), watermark column" },
    { name = "status", type = "string", comment = "booked | picked_up | in_transit | delivered | exception" },
    { name = "origin_port", type = "string" },
    { name = "destination_port", type = "string" },
    { name = "carrier", type = "string" },
    { name = "weight_kg", type = "double" },
    { name = "ingest_seq", type = "bigint", comment = "Tie-breaker for events with equal event_ts" },
  ]
}

module "kms" {
  source = "../../modules/kms"

  name       = local.name
  account_id = local.account_id
  region     = var.region
  partition  = local.partition
  tags       = local.tags
}

module "raw" {
  source = "../../modules/s3_zone"

  name_prefix   = local.name_prefix
  zone          = "raw"
  kms_key_arn   = module.kms.key_arn
  force_destroy = var.force_destroy_buckets
  tags          = local.tags
}

module "curated" {
  source = "../../modules/s3_zone"

  name_prefix   = local.name_prefix
  zone          = "curated"
  kms_key_arn   = module.kms.key_arn
  force_destroy = var.force_destroy_buckets
  tags          = local.tags
}

module "artifacts" {
  source = "../../modules/s3_zone"

  name_prefix   = local.name_prefix
  zone          = "artifacts"
  kms_key_arn   = module.kms.key_arn
  force_destroy = var.force_destroy_buckets
  tags          = local.tags
}

module "athena_results" {
  source = "../../modules/s3_zone"

  name_prefix                        = local.name_prefix
  zone                               = "athena-results"
  kms_key_arn                        = module.kms.key_arn
  force_destroy                      = var.force_destroy_buckets
  noncurrent_version_expiration_days = 7
  tags                               = local.tags
}

module "glue_catalog" {
  source = "../../modules/glue_catalog"

  database_name       = local.database_name
  description         = "Gulf Freight Co. curated zone (${var.environment})"
  table_name          = local.table_name
  curated_bucket_name = module.curated.bucket_name
  table_prefix        = local.curated_prefix
  columns             = local.shipment_columns
}

module "iam" {
  source = "../../modules/iam"

  name                 = local.name
  account_id           = local.account_id
  region               = var.region
  partition            = local.partition
  raw_bucket_arn       = module.raw.bucket_arn
  raw_read_prefix      = local.raw_prefix
  curated_bucket_arn   = module.curated.bucket_arn
  curated_write_prefix = local.curated_prefix
  artifacts_bucket_arn = module.artifacts.bucket_arn
  script_key           = local.script_key
  temp_prefix          = local.temp_prefix
  kms_key_arn          = module.kms.key_arn
  catalog_database_arn = module.glue_catalog.database_arn
  catalog_table_arn    = module.glue_catalog.table_arn
  tags                 = local.tags
}

module "glue_job" {
  source = "../../modules/glue_job"

  job_name              = "${local.name}-shipments-incremental"
  role_arn              = module.iam.glue_job_role_arn
  artifacts_bucket_name = module.artifacts.bucket_name
  script_key            = local.script_key
  script_source_path    = "${path.root}/../../../glue_jobs/shipments_incremental.py"
  temp_prefix           = local.temp_prefix
  kms_key_arn           = module.kms.key_arn
  warehouse_uri         = "s3://${module.curated.bucket_name}/"
  raw_path              = "s3://${module.raw.bucket_name}/${local.raw_prefix}"
  target_table          = "glue_catalog.${module.glue_catalog.database_name}.${module.glue_catalog.table_name}"
  lookback_hours        = var.glue_lookback_hours
  tags                  = local.tags
}

module "athena" {
  source = "../../modules/athena"

  name                           = "${local.name}-analysts"
  results_bucket_name            = module.athena_results.bucket_name
  kms_key_arn                    = module.kms.key_arn
  bytes_scanned_cutoff_per_query = var.athena_bytes_scanned_cutoff
  force_destroy                  = var.force_destroy_buckets
  tags                           = local.tags
}
