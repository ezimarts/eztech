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
  description = "Main website domain. "eziwebtech.com" 
  type        = string
  default     = ""
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID. Leave empty if DNS is managed outside Route 53."
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ARN of the SSL certificate in AWS ACM."
  type        = string
}

variable "certificate_secret_name" {
  type        = string
  description = "AWS Secrets Manager secret name"
}

variable "certificate_secret_name" {}


variable "website_bucket_name" {
  type = string
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

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type

variable "certificate_secret_name" {
  description = "Secrets Manager secret containing the SSL certificate"
  type        = string
}

variable "cloudfront_domain_name" {
  description = "Existing CloudFront domain, eziwebtech.com"
  type        = string
  default     = "eziwebtech.com"
}

variable "website_bucket_name" {
  description = "Name of the existing S3 bucket used as the CloudFront origin"
  type        = string
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID for eziwebtech.com"
  type        = string
}