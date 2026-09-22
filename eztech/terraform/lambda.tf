data "archive_file" "api_lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "api" {
  function_name    = "${var.project_name}-api"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.api_lambda_zip.output_path
  source_code_hash = data.archive_file.api_lambda_zip.output_base64sha256
  timeout          = 20

  environment {
    variables = {
      USERS_TABLE       = aws_dynamodb_table.users.name
      ORDERS_TABLE      = aws_dynamodb_table.orders.name
      PAYMENTS_TABLE    = aws_dynamodb_table.payments.name
      PRODUCTS_TABLE    = aws_dynamodb_table.products.name
      WEBSITE_BUCKET    = aws_s3_bucket.website.bucket
      SITE_DOMAIN       = var.domain_name
      ALLOWED_ORIGIN    = var.allowed_origin
      STRIPE_SECRET_KEY = var.stripe_secret_key
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy_attachment.lambda_dynamodb_attach,
    aws_iam_role_policy_attachment.lambda_s3_attach
  ]

  tags = local.common_tags
}
