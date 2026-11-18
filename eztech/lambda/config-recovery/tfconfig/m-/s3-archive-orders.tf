resource "aws_s3_bucket" "orders_archive" {
  bucket        = "${var.project_name}-orders-archive-${data.aws_caller_identity.current.account_id}"
  force_destroy = false

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-orders-archive"
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "orders_archive" {
  bucket                  = aws_s3_bucket.orders_archive.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "orders_archive" {
  bucket = aws_s3_bucket.orders_archive.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "orders_archive" {
  bucket = aws_s3_bucket.orders_archive.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
