output "distribution_id" {
  value = aws_cloudfront_distribution.this.id
}

output "distribution_domain" {
  value = aws_cloudfront_distribution.this.domain_name
}

output "site_url" {
  value = local.site_url
}

output "site_bucket" {
  value = aws_s3_bucket.site.id
}
