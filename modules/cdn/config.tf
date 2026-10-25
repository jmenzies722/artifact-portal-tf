data "aws_region" "current" {}

locals {
  site_url = "https://${aws_cloudfront_distribution.this.domain_name}"
}

# Runtime config, read by the static app at startup. Keeping these values out
# of the build means one web bundle works in every environment.
# Site uploads must not overwrite or delete it: `aws s3 sync --exclude config.json`.
resource "aws_s3_object" "config" {
  bucket        = aws_s3_bucket.site.id
  key           = "config.json"
  content_type  = "application/json"
  cache_control = "no-cache" # always revalidate, so config changes show up at once
  content = jsonencode({
    apiBase       = "/api"
    cognitoDomain = var.cognito_domain
    clientId      = var.web_client_id
    redirectUri   = "${local.site_url}/callback/"
    logoutUri     = "${local.site_url}/"
    region        = data.aws_region.current.region
  })
}
