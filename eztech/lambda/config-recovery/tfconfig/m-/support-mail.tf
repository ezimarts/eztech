locals {
  support_address       = "support@${var.domain_name}"
  support_mail_rule_set = "${var.project_name}-inbound-mail"
  support_mail_rule     = "forward-support"
  support_mail_rule_arn = "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:receipt-rule-set/${local.support_mail_rule_set}:receipt-rule/${local.support_mail_rule}"
  support_mail_prefix   = "inbound/"
}

resource "aws_ses_domain_identity" "support" {
  domain = var.domain_name
}

resource "aws_route53_record" "support_verification" {
  zone_id = var.hosted_zone_id
  name    = "_amazonses.${var.domain_name}"
  type    = "TXT"
  ttl     = 300
  records = [aws_ses_domain_identity.support.verification_token]
}

resource "aws_ses_domain_identity_verification" "support" {
  domain     = aws_ses_domain_identity.support.id
  depends_on = [aws_route53_record.support_verification]
}

resource "aws_s3_bucket" "support_mail" {
  bucket = "${var.project_name}-support-mail-${data.aws_caller_identity.current.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "support_mail" {
  bucket                  = aws_s3_bucket.support_mail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "support_mail" {
  bucket = aws_s3_bucket.support_mail.id

  rule {
    id     = "expire-inbound-mail"
    status = "Enabled"

    filter {
      prefix = local.support_mail_prefix
    }

    expiration {
      days = 30
    }
  }
}

resource "aws_s3_bucket_policy" "support_mail" {
  bucket = aws_s3_bucket.support_mail.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ses.amazonaws.com" }
      Action    = "s3:PutObject"
      Resource  = "${aws_s3_bucket.support_mail.arn}/${local.support_mail_prefix}*"
      Condition = {
        StringEquals = { "AWS:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnEquals    = { "AWS:SourceArn" = local.support_mail_rule_arn }
      }
    }]
  })
}

resource "aws_iam_role" "support_mail" {
  name = "${var.project_name}-support-mail"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_cloudwatch_log_group" "support_mail" {
  name              = "/aws/lambda/${var.project_name}-support-mail"
  retention_in_days = 30
}

resource "aws_iam_role_policy" "support_mail" {
  name = "forward-support-mail"
  role = aws_iam_role.support_mail.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.support_mail.arn}/${local.support_mail_prefix}*"
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = aws_ses_email_identity.sender.arn
        Condition = {
          "ForAllValues:StringEquals" = { "ses:Recipients" = local.support_recipient }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.support_mail.arn}:*"
      },
    ]
  })
}

data "archive_file" "support_mail" {
  type        = "zip"
  source_file = "${path.module}/lambda/support_mail.py"
  output_path = "${path.module}/support-mail.zip"
}

resource "aws_lambda_function" "support_mail" {
  function_name    = "${var.project_name}-support-mail"
  role             = aws_iam_role.support_mail.arn
  handler          = "support_mail.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.support_mail.output_path
  source_code_hash = data.archive_file.support_mail.output_base64sha256
  timeout          = 30
  memory_size      = 512

  environment {
    variables = {
      MAIL_BUCKET       = aws_s3_bucket.support_mail.bucket
      MAIL_PREFIX       = local.support_mail_prefix
      SUPPORT_ADDRESS   = local.support_address
      SUPPORT_RECIPIENT = local.support_recipient
      SENDER_EMAIL      = var.sender_email
    }
  }

  depends_on = [aws_iam_role_policy.support_mail]
}

resource "aws_lambda_permission" "support_mail" {
  statement_id   = "AllowSupportMailReceiptRule"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.support_mail.function_name
  principal      = "ses.amazonaws.com"
  source_account = data.aws_caller_identity.current.account_id
  source_arn     = local.support_mail_rule_arn
}

resource "aws_ses_receipt_rule_set" "support_mail" {
  rule_set_name = local.support_mail_rule_set
}

resource "aws_ses_receipt_rule" "support_mail" {
  name          = local.support_mail_rule
  rule_set_name = aws_ses_receipt_rule_set.support_mail.rule_set_name
  recipients    = [local.support_address]
  enabled       = true
  scan_enabled  = true

  s3_action {
    position          = 1
    bucket_name       = aws_s3_bucket.support_mail.bucket
    object_key_prefix = local.support_mail_prefix
  }

  lambda_action {
    position        = 2
    function_arn    = aws_lambda_function.support_mail.arn
    invocation_type = "Event"
  }

  depends_on = [
    aws_ses_domain_identity_verification.support,
    aws_s3_bucket_policy.support_mail,
    aws_lambda_permission.support_mail,
  ]
}

resource "aws_ses_active_receipt_rule_set" "support_mail" {
  rule_set_name = aws_ses_receipt_rule_set.support_mail.rule_set_name
  depends_on    = [aws_ses_receipt_rule.support_mail]
}

resource "aws_route53_record" "support_mx" {
  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "MX"
  ttl     = 300
  records = ["10 inbound-smtp.${var.aws_region}.amazonaws.com"]

  depends_on = [aws_ses_active_receipt_rule_set.support_mail]
}
