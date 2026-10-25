variable "name_prefix" {
  description = "Prefix for resource names, e.g. artifact-portal-dev"
  type        = string
}

variable "admin_role_arns" {
  description = "IAM principals allowed to administer the KMS key"
  type        = list(string)
}

variable "noncurrent_days" {
  description = "Days to keep old object versions"
  type        = number
  default     = 30
}
