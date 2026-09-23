# The public front door. One CloudFront distribution serves BOTH the static React site (S3)
# and the API (/api/* -> ALB) from a single domain, so there is no CORS and no second
# hostname for clients to trust.
#
# This lives in the always-on foundation stack, while the ALB lives in the nightly-destroyed
# API stack. They are joined by a stable DNS name (api-origin.<site>) that the API stack
# points at whichever ALB currently exists. When the API is down, /api/* returns 502 and the
# site itself keeps loading.

variable "env" { type = string }
variable "zone_name" { type = string }
variable "site_hostname" { type = string }

data "aws_route53_zone" "main" {
  name         = var.zone_name
  private_zone = false
}

locals {
  origin_hostname = "api-origin.${var.site_hostname}"
}

# --- TLS: one certificate covers the site (CloudFront) and the API origin (ALB). Both live
# in us-east-1, which is where CloudFront requires its certificates.
resource "aws_acm_certificate" "main" {
  domain_name               = var.site_hostname
  subject_alternative_names = [local.origin_hostname]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for o in aws_acm_certificate.main.domain_validation_options : o.domain_name => {
      name   = o.resource_record_name
      type   = o.resource_record_type
      record = o.resource_record_value
    }
  }
  zone_id         = data.aws_route53_zone.main.zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 60
  records         = [each.value.record]
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

# --- Only CloudFront may talk to the ALB: it must present this secret header.
resource "random_password" "origin_verify" {
  length  = 48
  special = false
}

# --- Static site bucket (private; CloudFront reads it via Origin Access Control)
data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "web" {
  bucket        = "afterhourz-${var.env}-web-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.env != "prod"
}

resource "aws_s3_bucket_public_access_block" "web" {
  bucket                  = aws_s3_bucket.web.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "web" {
  bucket = aws_s3_bucket.web.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "afterhourz-${var.env}-web"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_iam_policy_document" "web" {
  statement {
    sid       = "AllowCloudFrontRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.web.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.main.arn]
    }
  }
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.web.arn, "${aws_s3_bucket.web.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id
  policy = data.aws_iam_policy_document.web.json
}

# --- SPA routing. A CloudFront *Function* on the S3 behavior rewrites deep links (/book,
# /admin) to /index.html. We deliberately do NOT use distribution-level custom error pages:
# those would also rewrite genuine 403/404 responses from the API into index.html.
resource "aws_cloudfront_function" "spa_rewrite" {
  name    = "afterhourz-${var.env}-spa-rewrite"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-JS
    function handler(event) {
      var request = event.request;
      var uri = request.uri;
      if (uri.indexOf('.') === -1) {
        request.uri = '/index.html';
      }
      return request;
    }
  JS
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}
data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}
data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

resource "aws_cloudfront_response_headers_policy" "security" {
  name = "afterhourz-${var.env}-security-headers"

  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 31536000
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
  }

  custom_headers_config {
    items {
      header   = "Permissions-Policy"
      value    = "camera=(), microphone=(), geolocation=()"
      override = true
    }
    # Report-Only first: Google sign-in and GA4 need specific hosts. Load the site, check the
    # browser console for violations, then rename this header to Content-Security-Policy.
    items {
      header   = "Content-Security-Policy-Report-Only"
      value    = "default-src 'self'; script-src 'self' https://accounts.google.com https://www.googletagmanager.com; style-src 'self' 'unsafe-inline' https://accounts.google.com; img-src 'self' data: https:; connect-src 'self' https://accounts.google.com https://*.google-analytics.com https://*.analytics.google.com https://www.googletagmanager.com; frame-src https://accounts.google.com; base-uri 'self'; form-action 'self' https://checkout.stripe.com"
      override = true
    }
    dynamic "items" {
      for_each = var.env == "prod" ? [] : [1]
      content {
        header   = "X-Robots-Tag"
        value    = "noindex, nofollow" # never let Google index dev
        override = true
      }
    }
  }
}

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  http_version        = "http2and3"
  price_class         = "PriceClass_100" # US/Canada/Europe edges: cheapest, right for a Miami shop
  aliases             = [var.site_hostname]
  default_root_object = "index.html"
  comment             = "afterhourz ${var.env}"

  origin {
    origin_id                = "web"
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  origin {
    origin_id   = "api"
    domain_name = local.origin_hostname

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
    custom_header {
      name  = "X-Origin-Verify"
      value = random_password.origin_verify.result
    }
  }

  default_cache_behavior {
    target_origin_id           = "web"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
    compress                   = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_rewrite.arn
    }
  }

  ordered_cache_behavior {
    path_pattern               = "/api/*"
    target_origin_id           = "api"
    viewer_protocol_policy     = "https-only"
    allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
    compress                   = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.main.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

resource "aws_route53_record" "site_a" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.site_hostname
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "site_aaaa" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.site_hostname
  type    = "AAAA"
  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

output "zone_id" { value = data.aws_route53_zone.main.zone_id }
output "origin_hostname" { value = local.origin_hostname }
output "certificate_arn" { value = aws_acm_certificate_validation.main.certificate_arn }
output "origin_verify_secret" {
  value     = random_password.origin_verify.result
  sensitive = true
}
output "web_bucket" { value = aws_s3_bucket.web.bucket }
output "distribution_id" { value = aws_cloudfront_distribution.main.id }
output "site_url" { value = "https://${var.site_hostname}" }
