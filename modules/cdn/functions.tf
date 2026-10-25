# CloudFront Functions run at the edge on every request, for a fraction of
# Lambda@Edge's cost and latency. Plain URI rewrites are all we need here.
resource "aws_cloudfront_function" "strip_api_prefix" {
  name    = "${var.name_prefix}-strip-api-prefix"
  runtime = "cloudfront-js-2.0"
  comment = "Strip /api so /api/files reaches the API as /files"
  publish = true
  code    = file("${path.module}/functions/strip_api_prefix.js")
}

resource "aws_cloudfront_function" "rewrite_index" {
  name    = "${var.name_prefix}-rewrite-index"
  runtime = "cloudfront-js-2.0"
  comment = "Map trailing-slash and extensionless paths to index.html"
  publish = true
  code    = file("${path.module}/functions/rewrite_index.js")
}
