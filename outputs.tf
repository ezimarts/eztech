output "website_bucket_name" {
  value = aws_s3_bucket.website.bucket
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.cdn.id
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.cdn.domain_name
}

output "api_invoke_url" {
  value = aws_api_gateway_stage.prod.invoke_url
}

output "api_status_endpoint" {
  value = "${aws_api_gateway_stage.prod.invoke_url}/status"
}

output "users_endpoint" {
  value = "${aws_api_gateway_stage.prod.invoke_url}/users"
}

output "login_endpoint" {
  value = "${aws_api_gateway_stage.prod.invoke_url}/login"
}

output "orders_endpoint" {
  value = "${aws_api_gateway_stage.prod.invoke_url}/orders"
}

output "payments_endpoint" {
  value = "${aws_api_gateway_stage.prod.invoke_url}/payments"
}

output "checkout_endpoint" {
  value = "${aws_api_gateway_stage.prod.invoke_url}/checkout"
}

output "upload_website_command" {
  value = "aws s3 sync ./frontend s3://${aws_s3_bucket.website.bucket} --delete && aws cloudfront create-invalidation --distribution-id ${aws_cloudfront_distribution.cdn.id} --paths '/*'"
}

output "certificate_arn" {
  description = "ACM certificate ARN used for the website, when one is managed by this module."
  value       = try(aws_acm_certificate.website[0].arn, var.certificate_arn)
}
