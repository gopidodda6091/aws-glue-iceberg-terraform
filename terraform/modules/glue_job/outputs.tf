output "job_name" {
  description = "Glue job name."
  value       = aws_glue_job.this.name
}

output "script_s3_uri" {
  description = "Where the job script was uploaded."
  value       = "s3://${var.artifacts_bucket_name}/${aws_s3_object.script.key}"
}

output "security_configuration" {
  description = "Name of the Glue security configuration."
  value       = aws_glue_security_configuration.this.name
}
