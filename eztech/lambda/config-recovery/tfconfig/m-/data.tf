data "aws_caller_identity" "current" {}

data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}
