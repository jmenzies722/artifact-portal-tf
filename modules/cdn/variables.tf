variable "name_prefix" {
  description = "Prefix for resource names, e.g. artifact-portal-dev"
  type        = string
}

variable "api_endpoint" {
  description = "HTTP API endpoint, e.g. https://abc123.execute-api.us-east-1.amazonaws.com"
  type        = string
}

variable "cognito_domain" {
  description = "Cognito hosted login origin, e.g. https://<prefix>.auth.us-east-1.amazoncognito.com"
  type        = string

  # It goes verbatim into the CSP and config.json, so it must be a full origin.
  validation {
    condition     = startswith(var.cognito_domain, "https://")
    error_message = "cognito_domain must start with https://."
  }
}

variable "web_client_id" {
  description = "Cognito app client id used by the browser (PKCE, no secret)"
  type        = string
}
