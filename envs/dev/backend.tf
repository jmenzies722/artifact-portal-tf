terraform {
  backend "s3" {
    bucket       = "artifact-portal-tfstate-755484097925"
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true # S3-native locking, no DynamoDB table
  }
}
