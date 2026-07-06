# EZIMarts Full Terraform Stack

This stack creates:

- Private S3 bucket for static website files
- CloudFront distribution with Origin Access Control
- Optional ACM certificate and Route 53 records for `ezimarts.com`
- DynamoDB tables: users, orders, payments, products
- Python Lambda API
- API Gateway routes: `/users`, `/login`, `/orders`, `/payments`, `/checkout`
- Updated frontend `index.html` with Stripe and PayPal starter buttons

## Important payment note

Use Stripe Checkout or PayPal hosted checkout in production. Do not store credit card numbers in DynamoDB. This starter stores only order/payment metadata such as amount, provider, status, and provider reference.

## Deploy

```bash
terraform init
terraform plan
terraform apply
```

## Upload frontend after apply

Use the Terraform output command:

```bash
terraform output -raw upload_website_command
```

Then run the printed command.

## Update frontend placeholders

After `terraform apply`, replace this in `frontend/index.html`:

```text
REPLACE_WITH_TERRAFORM_API_INVOKE_URL
```

with:

```bash
terraform output -raw api_invoke_url
```

Also replace:

```text
REPLACE_WITH_PAYPAL_CLIENT_ID
pk_test_REPLACE_ME
```

with your real PayPal client ID and Stripe publishable key.

## Test API

```bash
curl -X POST "$(terraform output -raw users_endpoint)" \
  -H "Content-Type: application/json" \
  -d '{"name":"John","email":"john@test.com","phone":"1234567890"}'

curl -X POST "$(terraform output -raw orders_endpoint)" \
  -H "Content-Type: application/json" \
  -d '{"email":"john@test.com","amount":49.99,"currency":"USD","items":[{"name":"Website Starter","qty":1}]}'

curl -X POST "$(terraform output -raw payments_endpoint)" \
  -H "Content-Type: application/json" \
  -d '{"email":"john@test.com","amount":49.99,"currency":"USD","provider":"stripe","status":"paid"}'
```
