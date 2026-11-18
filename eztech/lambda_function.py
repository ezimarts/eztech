import base64
import json
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from html import escape

import boto3


dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
ses = boto3.client("ses")

USERS_TABLE = dynamodb.Table(os.environ["USERS_TABLE"])
ORDERS_TABLE = dynamodb.Table(os.environ["ORDERS_TABLE"])
PAYMENTS_TABLE = dynamodb.Table(os.environ["PAYMENTS_TABLE"])
PRODUCTS_TABLE = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
COUNTERS_TABLE = dynamodb.Table(os.environ["COUNTERS_TABLE"])

WEBSITE_BUCKET = os.environ.get("WEBSITE_BUCKET", "")
ORDERS_ARCHIVE_BUCKET = os.environ.get("ORDERS_ARCHIVE_BUCKET", "")
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "eziwebtech.com")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://eziwebtech.com")
BUSINESS_EMAIL = os.environ.get("BUSINESS_EMAIL", "ezimarts.info@gmail.com")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "zahidullah67@gmail.com")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
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

    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [customer_email]},
        ReplyToAddresses=[BUSINESS_EMAIL],
        Message={
            "Subject": {"Data": "We received your project request"},
            "Body": {
                "Html": {
                    "Data": f"""
                        <p>Hi {customer_name},</p>
                        <p>Thank you for contacting us. We received your request for
                        <strong>{service}</strong> and will get back to you shortly.</p>
                        <p>Your reference number is <strong>{order_id}</strong>.</p>
                        <p>Best,<br>EziWebTech</p>
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
    try:
        method = request_method(event)
        path = request_path(event)

        if method == "OPTIONS":
            return response(200, {"message": "CORS OK"})
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
