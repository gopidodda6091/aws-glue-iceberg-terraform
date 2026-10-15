output "kms_key_arn" {
  description = "Lake KMS key."
  value       = module.kms.key_arn
}

output "buckets" {
  description = "Zone bucket names."
  value = {
    raw            = module.raw.bucket_name
    curated        = module.curated.bucket_name
    artifacts      = module.artifacts.bucket_name
    athena_results = module.athena_results.bucket_name
  }
}

output "glue_job_name" {
  description = "Incremental shipments job."
  value       = module.glue_job.job_name
}

output "athena_workgroup" {
  description = "Athena workgroup for analysts."
  value       = module.athena.workgroup_name
}
