output "website_bucket_name" {
  value = aws_s3_bucket.website.bucket
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.website.id
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.website.domain_name
}

output "api_invoke_url" {
  value = aws_api_gateway_stage.prod.invoke_url
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
  value = "aws s3 sync ./frontend s3://${aws_s3_bucket.website.bucket} --delete && aws cloudfront create-invalidation --distribution-id ${aws_cloudfront_distribution.website.id} --paths '/*'"
}

output "certificate_arn" {
  description = "Imported ACM certificate ARN"
  value       = aws_acm_certificate.eziwebtech.arn
}
