EZIMarts web-services site using the AWS serverless stack you’re already building: S3/CloudFront frontend, API Gateway/Lambda backend, DynamoDB storage, and Terraform deployment.

Yes. For your website, the full stack should be:

Frontend

HTML + CSS + JavaScript
Hosted on S3
Delivered by CloudFront
Domain through Route 53
SSL through ACM

Backend

API Gateway
AWS Lambda Python
DynamoDB
IAM role/policy
CloudWatch Logs

Main features to build

1. Homepage
2. Services page
3. Contact / consultation form
4. Customer inquiry storage in DynamoDB
5. Admin view to see submitted requests
6. Email notification using SES
7. Terraform deployment

Recommended project structure

ezimarts-web-services/
│
├── frontend/
│   ├── index.html
│   ├── services.html
│   ├── contact.html
│   ├── admin.html
│   ├── style.css
│   └── app.js
│
├── terraform/
│   ├── main.tf
│   ├── provider.tf
│   ├── s3.tf
│   ├── cloudfront.tf
│   ├── route53.tf
│   ├── acm.tf
│   ├── dynamodb.tf
│   ├── lambda.tf
│   ├── api-gateway.tf
│   ├── iam.tf
│   └── outputs.tf
│
└── lambda/
    ├── create_inquiry.py
    ├── list_inquiries.py
    └── requirements.txt

DynamoDB table

Table name: ezimarts-inquiries
Partition key: inquiryId

Fields:

inquiryId
name
email
phone
businessName
websiteType
message
createdAt
status

API routes

POST /inquiries       Submit customer inquiry
GET  /inquiries       Admin view inquiries
GET  /health          Test API

Example customer flow

Customer visits ezimarts.com
↓
Reads website development services
↓
Submits consultation form
↓
API Gateway calls Lambda
↓
Lambda saves request in DynamoDB
↓
Admin page displays inquiries

First backend feature to build

Start with this:

Contact form → API Gateway → Lambda → DynamoDB

This is the most important part because it lets customers send you requests.

Your frontend form will post data like this:

{
  "name": "John Smith",
  "email": "john@example.com",
  "phone": "1234567890",
  "businessName": "Smith Roofing LLC",
  "websiteType": "Small Business Website",
  "message": "I need a website for my company."
}

I recommend building it in this order:

1. Frontend contact form
2. DynamoDB table
3. Lambda function
4. API Gateway POST method
5. CORS configuration
6. CloudWatch troubleshooting
7. Admin inquiry page
8. SES email notification
9. Terraform automation

DNS Configuration: 
"Domain name","CNAME name","Type","CNAME value"
"eziwebtech.com","_3648bd2b2b4bd8174a62a86a12b283ac.eziwebtech.com.","CNAME","_57799f69050be91ccfdb67c60a81169a.jkddzztszm.acm-validations.aws."
## Client portal and form delivery

The client portal uses Cognito email verification and shows applications created in the portal. The public consultation form continues to save submissions in the existing orders table.

To update a portal application, open DynamoDB in the EZTech AWS account in us-east-1, select the table named by the `client_applications_table` Terraform output, and find the item using the application reference from the notification. Edit its `status` field (for example, In review, Approved, or Closed). Clients see the new status when they select **Refresh status**.

Amazon SES is in the sandbox. Open the AWS verification links in ezmart.info@gmail.com and admin.ezmartllc@gmail.com before testing either form. Project submissions are saved even when SES rejects a notification. The support form reports sending errors and keeps the message available to retry. Application and notification errors appear in the EZTech API Lambda logs.

Direct email to support@eziwebtech.com goes through the domain's SES MX record and forwards to admin.ezmartllc@gmail.com. SES stores the original in the private EZTech support mail bucket for 30 days. Check the support mail Lambda logs and recover the original from S3 if forwarding fails or SES flags the message.

After a frontend deployment, invalidate the CloudFront distribution's homepage and portal assets if an edge still serves the previous version:

```powershell
$distribution = terraform output -raw cloudfront_distribution_id
aws cloudfront create-invalidation --profile eztech --distribution-id $distribution --paths '/' '/index.html' '/portal.js' '/portal-config.js'
```
