locals {
  # Browser uploads/downloads go straight to S3 via presigned URLs
  # (virtual-hosted style, so <bucket>.s3[.region].amazonaws.com).
  s3_presigned = "https://*.s3.amazonaws.com https://*.s3.us-east-1.amazonaws.com"

  # 'unsafe-inline' for scripts is a deliberate trade-off: Next.js static
  # export inlines its bootstrap/RSC payload scripts, and without a server
  # there is no per-request nonce. Everything else stays locked to 'self'.
  csp = join("; ", [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self' data:",
    "connect-src 'self' ${var.cognito_domain} ${local.s3_presigned}",
    "form-action 'self' ${var.cognito_domain}",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
  ])
}

resource "aws_cloudfront_response_headers_policy" "security" {
  name    = "${var.name_prefix}-security-headers"
  comment = "HSTS, CSP, nosniff, no framing"

  # override = true: CloudFront's value wins over anything the origin sends.
  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 31536000 # 1 year
      include_subdomains         = true
      override                   = true
    }
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    content_security_policy {
      content_security_policy = local.csp
      override                = true
    }
  }
}
