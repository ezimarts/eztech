data "aws_caller_identity" "current" {}

locals {
  common_tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
    Website   = var.domain_name
  }

  api_routes = {
    users    = "users"
    login    = "login"
    orders   = "orders"
    payments = "payments"
    checkout = "checkout"
    status   = "status"
  }
}
