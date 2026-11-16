resource "aws_cognito_user_pool" "clients" {
  name                     = "${var.project_name}-clients"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  deletion_protection      = "ACTIVE"

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }

  tags = local.common_tags
}

resource "aws_cognito_user_pool_domain" "clients" {
  domain       = "eztech-clients-939365918012"
  user_pool_id = aws_cognito_user_pool.clients.id
}

resource "aws_cognito_user_pool_client" "portal" {
  name                                 = "client-portal"
  user_pool_id                         = aws_cognito_user_pool.clients.id
  generate_secret                      = false
  prevent_user_existence_errors        = "ENABLED"
  supported_identity_providers         = ["COGNITO"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email"]
  callback_urls                        = ["${var.allowed_origin}/", "https://www.${var.domain_name}/"]
  logout_urls                          = ["${var.allowed_origin}/", "https://www.${var.domain_name}/"]
  id_token_validity                    = 15
  access_token_validity                = 15

  token_validity_units {
    id_token     = "minutes"
    access_token = "minutes"
  }
}

resource "aws_dynamodb_table" "client_applications" {
  name                        = "${var.project_name}-client-applications"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "owner"
  range_key                   = "applicationId"
  deletion_protection_enabled = true

  attribute {
    name = "owner"
    type = "S"
  }

  attribute {
    name = "applicationId"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = local.common_tags
}

resource "aws_api_gateway_authorizer" "clients" {
  name                           = "client-accounts"
  rest_api_id                    = aws_api_gateway_rest_api.api.id
  type                           = "COGNITO_USER_POOLS"
  provider_arns                  = [aws_cognito_user_pool.clients.arn]
  identity_source                = "method.request.header.Authorization"
  identity_validation_expression = "^${aws_cognito_user_pool_client.portal.id}$"
}

locals {
  client_application_methods = {
    GET     = "COGNITO_USER_POOLS"
    POST    = "COGNITO_USER_POOLS"
    OPTIONS = "NONE"
  }
}

resource "aws_api_gateway_resource" "applications" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "applications"
}

resource "aws_api_gateway_method" "applications" {
  for_each      = local.client_application_methods
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.applications.id
  http_method   = each.key
  authorization = each.value
  authorizer_id = each.value == "NONE" ? null : aws_api_gateway_authorizer.clients.id
}

resource "aws_api_gateway_integration" "applications" {
  for_each                = aws_api_gateway_method.applications
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = each.value.resource_id
  http_method             = each.value.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api.invoke_arn
}

resource "aws_iam_role_policy" "client_portal" {
  name = "client-portal"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:Query"]
        Resource = aws_dynamodb_table.client_applications.arn
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = aws_ses_email_identity.sender.arn
      },
    ]
  })
}

locals {
  project_recipient = "ezmart.info@gmail.com"
  support_recipient = "admin.ezmartllc@gmail.com"
}

# SES requires recipient verification while this account is in the sandbox.
resource "aws_ses_email_identity" "form_recipients" {
  for_each = toset([local.project_recipient, local.support_recipient])
  email    = each.value
}

resource "aws_api_gateway_method" "support" {
  for_each      = toset(["OPTIONS", "POST"])
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.route["support"].id
  http_method   = each.key
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "support" {
  for_each                = aws_api_gateway_method.support
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = each.value.resource_id
  http_method             = each.value.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api.invoke_arn
}

resource "aws_api_gateway_method_settings" "support" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "support/POST"

  settings {
    throttling_burst_limit = 5
    throttling_rate_limit  = 1
  }
}

resource "aws_s3_object" "portal_script" {
  bucket       = aws_s3_bucket.website.id
  key          = "portal.js"
  source       = "${path.module}/portal.js"
  etag         = filemd5("${path.module}/portal.js")
  content_type = "text/javascript"
}

locals {
  portal_config = {
    api     = aws_api_gateway_stage.prod.invoke_url
    client  = aws_cognito_user_pool_client.portal.id
    cognito = "https://${aws_cognito_user_pool_domain.clients.domain}.auth.${var.aws_region}.amazoncognito.com"
  }
}

resource "aws_s3_object" "portal_config" {
  bucket        = aws_s3_bucket.website.id
  key           = "portal-config.js"
  content       = "window.EZI_PORTAL = ${jsonencode(local.portal_config)};"
  content_type  = "text/javascript"
  cache_control = "no-cache"
}

output "client_applications_table" {
  value = aws_dynamodb_table.client_applications.name
}
