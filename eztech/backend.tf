terraform {
  backend "s3" {
    bucket              = "eztech-terraform-state-939365918012-us-east-1"
    key                 = "eztech/terraform.tfstate"
    region              = "us-east-1"
    profile             = "eztech"
    allowed_account_ids = ["939365918012"]
    encrypt             = true
    use_lockfile        = true
  }
}
