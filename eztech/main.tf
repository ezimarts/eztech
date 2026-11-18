resource "aws_dynamodb_table" "requests" {
  name         = "eztech-requests"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "requestId"

  attribute {
    name = "requestId"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_ses_email_identity" "sender" {
  email = var.sender_email
}

resource "aws_iam_role" "lambda" {
  name = "${var.resource_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "${var.resource_prefix}-lambda-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = aws_dynamodb_table.requests.arn
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = "*"
        Condition = {
          StringEquals = { "ses:FromAddress" = var.sender_email }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${var.resource_prefix}:*"
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.resource_prefix}"
  retention_in_days = 30
}

resource "aws_lambda_function" "submit_request" {
  function_name    = var.resource_prefix
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.handler"
  runtime          = "python3.13"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 10
  memory_size      = 256

  environment {
    variables = {
      TABLE_NAME     = aws_dynamodb_table.requests.name
      BUSINESS_EMAIL = var.business_email
      SENDER_EMAIL   = var.sender_email
    }
  }

  depends_on = [aws_iam_role_policy.lambda, aws_cloudwatch_log_group.lambda]
}

resource "aws_apigatewayv2_api" "requests" {
  name          = "${var.resource_prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = [var.allowed_origin]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.requests.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.submit_request.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "submit" {
  api_id    = aws_apigatewayv2_api.requests.id
  route_key = "POST /requests"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.requests.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.submit_request.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.requests.execution_arn}/*/*"
}

output "submission_url" {
  description = "POST form submissions to this URL."
  value       = "${aws_apigatewayv2_api.requests.api_endpoint}/requests"
}

output "ses_verification_note" {
  value = "Open the verification email sent by AWS to ${var.sender_email} before testing email delivery."
}
