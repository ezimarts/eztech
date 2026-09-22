resource "aws_dynamodb_table" "users" {
  name                        = "${var.project_name}-users"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "email"
  deletion_protection_enabled = true

  attribute {
    name = "email"
    type = "S"
  }

  tags = local.common_tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_dynamodb_table" "orders" {
  name                        = "${var.project_name}-orders"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "orderId"
  deletion_protection_enabled = true

  attribute {
    name = "orderId"
    type = "S"
  }

  tags = local.common_tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_dynamodb_table" "payments" {
  name                        = "${var.project_name}-payments"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "paymentId"
  deletion_protection_enabled = true

  attribute {
    name = "paymentId"
    type = "S"
  }

  tags = local.common_tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_dynamodb_table" "products" {
  name                        = "${var.project_name}-products"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "productId"
  deletion_protection_enabled = true

  attribute {
    name = "productId"
    type = "S"
  }

  tags = local.common_tags

  lifecycle {
    prevent_destroy = true
  }
}
