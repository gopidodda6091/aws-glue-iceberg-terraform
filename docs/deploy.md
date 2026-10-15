# Deploying to a real AWS account (optional)

CI never touches AWS. Everything below is for someone who wants to stand the
stack up in their own sandbox account. **It creates billable resources** (KMS
key, S3 storage, Glue job runs, Athena scans). Tear it down when finished.

## Prerequisites

- Terraform >= 1.6 (CI uses 1.9.8) or OpenTofu >= 1.6
- An AWS CLI profile with rights to create KMS keys, S3 buckets, IAM roles,
  Glue and Athena resources in the target region
- Python 3.11 if you want to generate sample data (`make data`)

## 1. Remote state (recommended)

The dev environment ships with local state so CI and LocalStack runs need no
backend. For a shared account, add a backend block to
`terraform/envs/dev/providers.tf`:

```hcl
terraform {
  backend "s3" {
    bucket       = "<your-state-bucket>"
    key          = "gulf-freight/dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true # Terraform >= 1.10; use dynamodb_table on older versions
  }
}
```

## 2. Plan and apply

```bash
export AWS_PROFILE=<your-sandbox-profile>
cd terraform/envs/dev
terraform init
terraform plan -out=dev.tfplan          # use_localstack defaults to false
terraform apply dev.tfplan
```

Useful variables (see `variables.tf`):

| Variable | Default | Notes |
|---|---|---|
| `region` | `us-east-1` | |
| `athena_bytes_scanned_cutoff` | 1 GiB | Queries scanning more are cancelled |
| `glue_lookback_hours` | 6 | Late-event window re-read on each run |
| `force_destroy_buckets` | `false` | Set `true` only in throwaway accounts |

## 3. Land sample data and run the job

Bucket names follow `gulf-freight-dev-<account-id>-<zone>`. Uploads must use
SSE-KMS with the lake key, or the bucket policy rejects them:

```bash
make data
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
KEY=$(terraform -chdir=terraform/envs/dev output -raw kms_key_arn)
aws s3 cp data/raw/shipments "s3://gulf-freight-dev-${ACCOUNT}-raw/shipments/" \
  --recursive --sse aws:kms --sse-kms-key-id "$KEY"
aws glue start-job-run --job-name gulf-freight-dev-shipments-incremental
```

Query the result in the Athena console using the `gulf-freight-dev-analysts`
workgroup:

```sql
SELECT status, count(*) FROM gulf_freight_dev_curated.shipments GROUP BY 1;
```

## 4. Who can do what

| Principal | Access |
|---|---|
| Glue job role | `s3:GetObject` on `raw` bucket `shipments/*`; read/write on `curated` bucket `shipments/*`; the one script object and its temp prefix in `artifacts`; `kms:Decrypt/Encrypt/GenerateDataKey/DescribeKey` on the lake key only; `glue:GetDatabase/GetTable/UpdateTable` on the curated database and `shipments` table only |
| Analysts | Grant `athena:StartQueryExecution` etc. scoped to the workgroup ARN (not managed here) |

## 5. Tear down

```bash
terraform -chdir=terraform/envs/dev destroy
```

Versioned buckets that still hold objects will block deletion unless
`force_destroy_buckets=true`. The KMS key enters a 30-day pending-deletion
window rather than disappearing immediately.
