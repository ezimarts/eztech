variable "aws_region" {
  description = "AWS region for Lambda, API Gateway, S3, and DynamoDB."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project prefix used for resource names."
  type        = string
  default     = "eztech"
}

variable "domain_name" {
  description = "Main website domain, for example eziwebtech.com."
  type        = string
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID for eziwebtech.com. Leave empty to skip DNS records."
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ARN of an existing ACM certificate in us-east-1 used by the CDN distribution."
  type        = string
  default     = ""
}

variable "website_bucket_name" {
  description = "Name of the S3 bucket used as the website origin."
  type        = string
}

variable "certificate_secret_name" {
  description = "AWS Secrets Manager secret name for certificate-related data, if used by this project."
  type        = string
}

variable "cloudfront_domain_name" {
  description = "CloudFront distribution domain name, for example d123abc.cloudfront.net. Do not use eziwebtech.com and do not include https://."
  type        = string
}

variable "stripe_publishable_key" {
  description = "Stripe publishable key used by frontend."
  type        = string
  default     = "pk_test_REPLACE_ME"
}

variable "stripe_secret_key" {
  description = "Stripe secret key for Lambda. Use terraform.tfvars or environment variable."
  type        = string
  default     = "sk_test_REPLACE_ME"
  sensitive   = true
}

variable "paypal_client_id" {
  description = "PayPal client ID used by frontend."
  type        = string
  default     = "REPLACE_WITH_PAYPAL_CLIENT_ID"
}

variable "api_stage_name" {
  description = "API Gateway deployment stage name."
  type        = string
  default     = "prod"
}

variable "allowed_origin" {
  description = "Allowed browser origin for Lambda API responses."
  type        = string
  default     = "https://eziwebtech.com"
}
