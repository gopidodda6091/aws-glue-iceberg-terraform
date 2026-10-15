output "glue_job_role_arn" {
  description = "ARN of the Glue job execution role."
  value       = aws_iam_role.glue_job.arn
}

output "glue_job_role_name" {
  description = "Name of the Glue job execution role."
  value       = aws_iam_role.glue_job.name
}

output "glue_job_policy_json" {
  description = "Rendered inline policy, exposed for review and policy tests."
  value       = data.aws_iam_policy_document.glue_job.json
}
