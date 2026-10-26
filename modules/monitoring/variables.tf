variable "name_prefix" {
  description = "Prefix for resource names, e.g. artifact-portal-dev"
  type        = string
}

variable "api_id" {
  description = "HTTP API id (AWS/ApiGateway ApiId dimension)"
  type        = string
}

variable "api_stage" {
  description = "HTTP API stage (AWS/ApiGateway Stage dimension)"
  type        = string
  default     = "$default"
}

variable "function_names" {
  description = "Lambda functions to alarm on, key -> function name"
  type        = map(string)
}

variable "distribution_id" {
  description = "CloudFront distribution id"
  type        = string
}

# Sensitive (public repo: keeps the address out of plans and CI logs). sns.tf
# uses nonsensitive() on the yes/no check only, so count still works.
variable "alert_email" {
  description = "Email subscribed to the alerts topic; empty means no subscription"
  type        = string
  default     = ""
  sensitive   = true
}

variable "availability_target" {
  description = "Availability SLO in percent of requests that are not 5xx"
  type        = number
  default     = 99.9
}

variable "latency_p95_ms" {
  description = "Latency SLO: p95 must stay under this many milliseconds"
  type        = number
  default     = 1000
}

variable "rotation_function_name" {
  description = "The CI secret rotation Lambda; alarmed on its own (any error pages)"
  type        = string
}
