resource "aws_iam_role_policy" "support_email_delivery" {
  name = "support-email-delivery"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Action" : "ses:SendEmail",
        "Condition" : {
          "StringEquals" : {
            "ses:FromAddress" : "zahidullah67@gmail.com"
          },
          "ForAllValues:StringEquals" : {
            "ses:Recipients" : [
              "admin.ezmartllc@gmail.com"
            ]
          }
        },
        "Resource" : [
          "arn:aws:ses:us-east-1:939365918012:identity/zahidullah67@gmail.com",
          "arn:aws:ses:us-east-1:939365918012:identity/admin.ezmartllc@gmail.com"
        ],
        "Effect" : "Allow"
      }
    ]
  })
}

import {
  to = aws_iam_role_policy.support_email_delivery
  id = "eztech-api-lambda-role:support-email-delivery"
}
