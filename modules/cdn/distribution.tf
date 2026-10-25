# AWS-managed policies, looked up by name rather than hard-coding their ids.
data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

# Forwards Authorization, query strings, etc., but not Host: API Gateway
# routes on its own hostname and would reject *.cloudfront.net.
data "aws_cloudfront_origin_request_policy" "all_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

locals {
  site_origin_id = "site"
  api_origin_id  = "api"
  api_domain     = trimprefix(var.api_endpoint, "https://")
}

# OAC: CloudFront signs every S3 request with SigV4 (successor to OAI).
resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${var.name_prefix}-site"
  description                       = "CloudFront -> private site bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "this" {
  enabled             = true
  comment             = "${var.name_prefix} portal"
  price_class         = "PriceClass_100" # NA + EU edges only: cheapest
  http_version        = "http2and3"
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  origin {
    origin_id                = local.site_origin_id
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  origin {
    origin_id   = local.api_origin_id
    domain_name = local.api_domain
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Static site.
  default_cache_behavior {
    target_origin_id           = local.site_origin_id
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.rewrite_index.arn
    }
  }

  # Same-origin API: the browser calls /api/*, so no CORS preflights.
  # https-only, not redirect: a 301 would make browsers replay POST/DELETE as GET.
  ordered_cache_behavior {
    path_pattern               = "/api/*"
    target_origin_id           = local.api_origin_id
    viewer_protocol_policy     = "https-only"
    allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_except_host.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.strip_api_prefix.arn
    }
  }

  # Only 404 is mapped, because these apply to /api/* too. Mapping 403 as well
  # would turn the API's RBAC "forbidden" into a "not found" HTML page. S3
  # returns 404 (not 403) for missing keys thanks to s3:ListBucket in bucket.tf.
  custom_error_response {
    error_code            = 404
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Default *.cloudfront.net certificate: no custom domain in the lab.
  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
