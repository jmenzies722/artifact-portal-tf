variable "name_prefix" {
  description = "Prefix for resource names, e.g. artifact-portal-dev"
  type        = string
}

variable "bucket_name" {
  description = "Artifacts bucket name"
  type        = string
}

variable "bucket_arn" {
  description = "Artifacts bucket ARN"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key that encrypts the artifacts bucket"
  type        = string
}

variable "issuer_url" {
  description = "Cognito user pool issuer, https://cognito-idp.<region>.amazonaws.com/<pool>"
  type        = string
}

variable "audiences" {
  description = "Accepted app client ids (aud for ID tokens, client_id for access tokens)"
  type        = list(string)
}

variable "cors_origins" {
  description = "Browser origins allowed to call the API"
  type        = list(string)
  default     = ["http://localhost:3000"]
}
