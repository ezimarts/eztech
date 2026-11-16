import base64
import json
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from html import escape

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
ses = boto3.client("ses")

USERS_TABLE = dynamodb.Table(os.environ["USERS_TABLE"])
ORDERS_TABLE = dynamodb.Table(os.environ["ORDERS_TABLE"])
PAYMENTS_TABLE = dynamodb.Table(os.environ["PAYMENTS_TABLE"])
PRODUCTS_TABLE = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
COUNTERS_TABLE = dynamodb.Table(os.environ["COUNTERS_TABLE"])
APPLICATIONS_TABLE = dynamodb.Table(os.environ["APPLICATIONS_TABLE"])

WEBSITE_BUCKET = os.environ.get("WEBSITE_BUCKET", "")
ORDERS_ARCHIVE_BUCKET = os.environ.get("ORDERS_ARCHIVE_BUCKET", "")
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "eziwebtech.com")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://eziwebtech.com")
BUSINESS_EMAIL = os.environ.get("BUSINESS_EMAIL", "ezimarts.info@gmail.com")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "zahidullah67@gmail.com")
SUPPORT_RECIPIENT = os.environ["SUPPORT_RECIPIENT"]

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST",
        },
        "body": json.dumps(body, default=str),
    }


def parse_body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)


def request_method(event):
    """Support API Gateway REST API (v1) and HTTP API (v2) events."""
    return (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method")
        or ""
    ).upper()


def request_path(event):
    """Support API Gateway REST API (v1) and HTTP API (v2) events."""
    return event.get("path") or event.get("rawPath") or ""


def clean_text(value, max_length):
    return " ".join(str(value or "").strip().split())[:max_length]


def clean_money(value):
    try:
        return Decimal(str(value or 0))
    except Exception as exc:
        raise ValueError("Invalid amount") from exc


def send_inquiry(recipient, reply_to, subject, message):
    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [recipient]},
        ReplyToAddresses=[reply_to],
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": message, "Charset": "UTF-8"}},
        },
    )


def contact_support(body):
    email = clean_text(body.get("email"), 254).lower()
    name = clean_text(body.get("name"), 100)
    subject = clean_text(body.get("subject"), 150)
    message = str(body.get("message") or "").strip()
    if not EMAIL_RE.fullmatch(email) or not name or not subject or not 1 <= len(message) <= 4000:
        return response(422, {"message": "Enter your name, email, subject, and a message of up to 4,000 characters."})

    try:
        send_inquiry(SUPPORT_RECIPIENT, email, f"EZI Web Tech support: {subject}", f"{name} <{email}>\n\n{message}")
    except ClientError as exc:
        print(json.dumps({"operation": "support_email", "code": exc.response["Error"]["Code"]}))
        return response(503, {"message": "We couldn't send your message. Please try again."})
    return response(200, {"message": "Your message was sent to support."})


def list_applications(owner, query):
    options = {
        "KeyConditionExpression": Key("owner").eq(owner),
        "ScanIndexForward": False,
        "Limit": 20,
        "ProjectionExpression": "applicationId, createdAt, service, #status",
        "ExpressionAttributeNames": {"#status": "status"},
    }
    cursor = query.get("before", "")
    if cursor:
        if not re.fullmatch(r"\d{20}-[a-f0-9]{32}", cursor):
            return response(400, {"message": "Invalid application cursor"})
        options["ExclusiveStartKey"] = {"owner": owner, "applicationId": cursor}
    result = APPLICATIONS_TABLE.query(**options)
    return response(200, {
        "applications": result["Items"],
        "next": result.get("LastEvaluatedKey", {}).get("applicationId"),
    })


def submit_application(owner, email, body):
    application_id = clean_text(body.get("applicationId"), 60)
    name = clean_text(body.get("name"), 100)
    service = clean_text(body.get("service"), 150)
    phone = clean_text(body.get("phone"), 40)
    message = str(body.get("message") or "").strip()
    if not re.fullmatch(r"\d{20}-[a-f0-9]{32}", application_id) or not name or not service or not 1 <= len(message) <= 4000:
        return response(422, {"message": "Enter your name, service, and a project description of up to 4,000 characters."})

    item = {
        "owner": owner,
        "applicationId": application_id,
        "email": email,
        "name": name,
        "service": service,
        "phone": phone,
        "message": message,
        "status": "Submitted",
        "createdAt": now_iso(),
    }
    try:
        APPLICATIONS_TABLE.put_item(Item=item, ConditionExpression="attribute_not_exists(applicationId)")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return response(200, {"applicationId": application_id})

    try:
        send_inquiry(
            BUSINESS_EMAIL, email, "New EZI Web Tech application",
            f"Reference: {application_id}\nName: {name}\nEmail: {email}\nPhone: {phone}\nService: {service}\n\n{message}",
        )
    except ClientError as exc:
        print(json.dumps({"operation": "application_email", "applicationId": application_id, "code": exc.response["Error"]["Code"]}))
    return response(201, {"applicationId": application_id})


def next_sequence(counter_name, start_at=100000):
    result = COUNTERS_TABLE.update_item(
        Key={"counterName": counter_name},
        UpdateExpression="SET currentValue = if_not_exists(currentValue, :start) + :inc",
        ExpressionAttributeValues={
            ":start": Decimal(start_at - 1),
            ":inc": Decimal(1),
        },
        ReturnValues="UPDATED_NEW",
    )
    return str(int(result["Attributes"]["currentValue"]))


def archive_order_to_s3(order):
    if not ORDERS_ARCHIVE_BUCKET:
        return None

    created_at = order.get("createdAt", now_iso())
    key = f"orders/{created_at[:4]}/{created_at[5:7]}/{order['orderId']}.json"
    s3.put_object(
        Bucket=ORDERS_ARCHIVE_BUCKET,
        Key=key,
        Body=json.dumps(order, default=str, indent=2).encode("utf-8"),
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )
    return key


def send_order_emails(order):
    customer_email = order["email"]
    customer_name = escape(order.get("customerName") or "Customer")
    safe_email = escape(customer_email)
    phone = escape(order.get("phone") or "Not provided")
    service = escape(order.get("service") or "New project")
    message = escape(order.get("message") or "Not provided")
    order_id = escape(str(order["orderId"]))

    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [BUSINESS_EMAIL]},
        ReplyToAddresses=[customer_email],
        Message={
            "Subject": {"Data": f"New project request from {order['customerName']}"},
            "Body": {
                "Html": {
                    "Data": f"""
                        <h2>New project request</h2>
                        <p><strong>Reference:</strong> {order_id}</p>
                        <p><strong>Name:</strong> {customer_name}<br>
                        <strong>Email:</strong> {safe_email}<br>
                        <strong>Phone:</strong> {phone}<br>
                        <strong>Service:</strong> {service}</p>
                        <p><strong>Project context:</strong><br>{message}</p>
                    """
                }
            },
        },
    )


def create_user(body):
    email = clean_text(body.get("email"), 254).lower()
    if not EMAIL_RE.match(email):
        return response(400, {"message": "A valid email is required"})

    item = {
        "email": email,
        "name": clean_text(body.get("name"), 100),
        "phone": clean_text(body.get("phone"), 40),
        "createdAt": now_iso(),
    }
    # Authentication must use Cognito; passwords are never saved here.
    USERS_TABLE.put_item(Item=item)
    return response(200, {"message": "User saved", "user": item})


def login_user(body):
    email = clean_text(body.get("email"), 254).lower()
    if not EMAIL_RE.match(email):
        return response(400, {"message": "A valid email is required"})
    result = USERS_TABLE.get_item(Key={"email": email})
    if "Item" not in result:
        return response(404, {"message": "User not found"})
    return response(200, {"message": "Login demo successful", "user": result["Item"]})


def create_order(body):
    # Accept both the original API names and the project form's newer names.
    customer_name = clean_text(body.get("customerName") or body.get("name"), 100)
    email = clean_text(body.get("email"), 254).lower()
    phone = clean_text(body.get("phone"), 40)
    service = clean_text(
        body.get("service") or body.get("helpWith") or body.get("help_with"),
        150,
    )
    message = clean_text(
        body.get("message")
        or body.get("projectContext")
        or body.get("project_context"),
        4000,
    )

    errors = {}
    if len(customer_name) < 2:
        errors["name"] = "Name is required"
    if not EMAIL_RE.match(email):
        errors["email"] = "A valid email is required"
    if not service:
        errors["service"] = "Service is required"
    if not message:
        errors["message"] = "Project context is required"
    if errors:
        return response(422, {"message": "Please correct the form fields", "errors": errors})

    order_id = clean_text(body.get("orderId"), 100) or next_sequence("orders")
    item = {
        "orderId": order_id,
        "email": email,
        "customerName": customer_name,
        "phone": phone,
        "service": service,
        "message": message,
        "source": clean_text(body.get("source") or "website", 100),
        "items": body.get("items") if isinstance(body.get("items"), list) else [],
        "amount": clean_money(body.get("amount", 0)),
        "currency": clean_text(body.get("currency") or "USD", 10).upper(),
        "status": clean_text(body.get("status") or "created", 50),
        "createdAt": now_iso(),
    }
    if service and not item["items"]:
        item["items"] = [{"name": service, "qty": 1, "notes": message}]

    # Saving the request is the required operation. Optional archive/email failures
    # must not cause the browser to submit a duplicate order.
    ORDERS_TABLE.put_item(
        Item=item,
        ConditionExpression="attribute_not_exists(orderId)",
    )

    archive_key = None
    try:
        archive_key = archive_order_to_s3(item)
    except Exception as exc:
        print(json.dumps({"level": "error", "orderId": order_id, "operation": "archive", "error": str(exc)}))

    email_sent = True
    try:
        send_order_emails(item)
    except Exception as exc:
        email_sent = False
        print(json.dumps({"level": "error", "orderId": order_id, "operation": "email", "error": str(exc)}))
    if email_sent:
        try:
            send_inquiry(
                email,
                BUSINESS_EMAIL,
                "We received your project request",
                f"Hi {customer_name},\n\nWe received your request for {service}. Your reference is {order_id}.\n\nEZI Web Tech",
            )
        except ClientError as exc:
            print(json.dumps({"operation": "customer_acknowledgment", "orderId": order_id, "code": exc.response["Error"]["Code"]}))

    return response(
        201,
        {
            "message": "Project request received. Thank you!",
            "order": item,
            "archiveKey": archive_key,
            "emailNotificationSent": email_sent,
        },
    )


def save_payment(body):
    payment_id = clean_text(body.get("paymentId"), 100) or f"pay_{uuid.uuid4().hex[:12]}"
    item = {
        "paymentId": payment_id,
        "orderId": clean_text(body.get("orderId"), 100),
        "email": clean_text(body.get("email") or "guest@ezimarts.com", 254).lower(),
        "amount": clean_money(body.get("amount", 0)),
        "currency": clean_text(body.get("currency") or "USD", 10).upper(),
        "provider": clean_text(body.get("provider") or "stripe", 50),
        "status": clean_text(body.get("status") or "pending", 50),
        "providerReference": clean_text(body.get("providerReference"), 200),
        "createdAt": now_iso(),
    }
    PAYMENTS_TABLE.put_item(Item=item)
    return response(200, {"message": "Payment record saved", "payment": item})


def create_checkout(body):
    """Starter endpoint; replace the placeholder URL with a server-created checkout session."""
    amount = clean_money(body.get("amount", 49.99))
    email = clean_text(body.get("email") or "guest@ezimarts.com", 254).lower()
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    payment_id = f"pay_{uuid.uuid4().hex[:12]}"

    ORDERS_TABLE.put_item(
        Item={
            "orderId": order_id,
            "email": email,
            "items": body.get("items", [{"name": "EZIMarts Website Starter", "qty": 1}]),
            "amount": amount,
            "currency": clean_text(body.get("currency") or "USD", 10).upper(),
            "status": "checkout_started",
            "createdAt": now_iso(),
        }
    )
    PAYMENTS_TABLE.put_item(
        Item={
            "paymentId": payment_id,
            "orderId": order_id,
            "email": email,
            "amount": amount,
            "currency": clean_text(body.get("currency") or "USD", 10).upper(),
            "provider": clean_text(body.get("provider") or "stripe", 50),
            "status": "checkout_started",
            "createdAt": now_iso(),
        }
    )
    return response(
        200,
        {
            "message": "Checkout started. Replace the URL with a real hosted checkout session.",
            "orderId": order_id,
            "paymentId": payment_id,
            "checkoutUrl": "https://checkout.stripe.com/replace-with-real-session-url",
        },
    )


def site_status():
    status = {
        "domain": SITE_DOMAIN,
        "bucket": WEBSITE_BUCKET,
        "tables": {
            "users": USERS_TABLE.name,
            "orders": ORDERS_TABLE.name,
            "payments": PAYMENTS_TABLE.name,
            "products": PRODUCTS_TABLE.name,
        },
    }
    if WEBSITE_BUCKET:
        try:
            s3.head_bucket(Bucket=WEBSITE_BUCKET)
            status["s3"] = "connected"
        except Exception:
            status["s3"] = "not_verified"
    return response(200, status)


def lambda_handler(event, context):
    result = route_request(event, context)
    headers = event.get("headers") or {}
    origin = next((value for name, value in headers.items() if name.lower() == "origin"), None)
    if origin == f"https://www.{SITE_DOMAIN}":
        result["headers"]["Access-Control-Allow-Origin"] = origin
    result["headers"]["Vary"] = "Origin"
    return result


def route_request(event, context):
    try:
        method = request_method(event)
        path = request_path(event)

        if method == "OPTIONS":
            return response(200, {"message": "CORS OK"})
        if path.endswith("/applications"):
            claims = event.get("requestContext", {}).get("authorizer", {}).get("claims") or {}
            if not claims.get("sub") or str(claims.get("email_verified")).lower() != "true":
                return response(403, {"message": "Sign in with a verified email to access your applications."})
            if method == "GET":
                return list_applications(claims["sub"], event.get("queryStringParameters") or {})
            if method == "POST":
                return submit_application(claims["sub"], claims["email"], parse_body(event))
        if method == "GET" and path.endswith("/status"):
            return site_status()
        if method != "POST":
            return response(405, {"message": "Method not allowed"})

        body = parse_body(event)
        if path.endswith("/users"):
            return create_user(body)
        if path.endswith("/login"):
            return login_user(body)
        if path.endswith("/orders"):
            return create_order(body)
        if path.endswith("/support"):
            return contact_support(body)
        if path.endswith("/payments"):
            return save_payment(body)
        if path.endswith("/checkout"):
            return create_checkout(body)
        return response(404, {"message": "Route not found", "path": path})

    except json.JSONDecodeError:
        return response(400, {"message": "Invalid JSON request"})
    except ValueError as exc:
        return response(400, {"message": str(exc)})
    except Exception as exc:
        request_id = getattr(context, "aws_request_id", "unknown")
        print(json.dumps({"level": "error", "requestId": request_id, "error": str(exc)}))
        return response(500, {"message": "Internal server error", "requestId": request_id})
