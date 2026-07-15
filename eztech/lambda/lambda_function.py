import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3

try:
    import urllib.request
except Exception:
    urllib = None


dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
USERS_TABLE = dynamodb.Table(os.environ["USERS_TABLE"])
ORDERS_TABLE = dynamodb.Table(os.environ["ORDERS_TABLE"])
PAYMENTS_TABLE = dynamodb.Table(os.environ["PAYMENTS_TABLE"])
PRODUCTS_TABLE = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
WEBSITE_BUCKET = os.environ.get("WEBSITE_BUCKET", "")
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "eziwebtech.com")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://eziwebtech.com")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")


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
        import base64
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)


def clean_money(value):
    return Decimal(str(value))


def create_user(body):
    email = body.get("email", "").strip().lower()
    if not email:
        return response(400, {"message": "email is required"})

    item = {
        "email": email,
        "name": body.get("name", ""),
        "phone": body.get("phone", ""),
        "createdAt": now_iso(),
    }
    # Demo only: do not store plain passwords in production. Use Amazon Cognito for real login.
    if body.get("password"):
        item["passwordDemoOnly"] = "Do not store passwords in DynamoDB. Use Cognito."

    USERS_TABLE.put_item(Item=item)
    return response(200, {"message": "User saved", "user": item})


def login_user(body):
    email = body.get("email", "").strip().lower()
    if not email:
        return response(400, {"message": "email is required"})
    result = USERS_TABLE.get_item(Key={"email": email})
    if "Item" not in result:
        return response(404, {"message": "User not found"})
    return response(200, {"message": "Login demo successful", "user": result["Item"]})


def create_order(body):
    order_id = body.get("orderId") or f"ord_{uuid.uuid4().hex[:12]}"
    item = {
        "orderId": order_id,
        "email": body.get("email", "guest@ezimarts.com"),
        "items": body.get("items", []),
        "amount": clean_money(body.get("amount", 0)),
        "currency": body.get("currency", "USD"),
        "status": body.get("status", "created"),
        "createdAt": now_iso(),
    }
    ORDERS_TABLE.put_item(Item=item)
    return response(200, {"message": "Order saved", "order": item})


def save_payment(body):
    payment_id = body.get("paymentId") or f"pay_{uuid.uuid4().hex[:12]}"
    item = {
        "paymentId": payment_id,
        "orderId": body.get("orderId", ""),
        "email": body.get("email", "guest@ezimarts.com"),
        "amount": clean_money(body.get("amount", 0)),
        "currency": body.get("currency", "USD"),
        "provider": body.get("provider", "stripe"),
        "status": body.get("status", "pending"),
        "providerReference": body.get("providerReference", ""),
        "createdAt": now_iso(),
    }
    PAYMENTS_TABLE.put_item(Item=item)
    return response(200, {"message": "Payment record saved", "payment": item})


def create_checkout(body):
    """
    Safe starter endpoint.
    Production Stripe Checkout should create a Stripe Checkout Session server-side.
    This demo records an order and payment intent placeholder so the site flow works.
    """
    amount = clean_money(body.get("amount", 49.99))
    email = body.get("email", "guest@ezimarts.com")
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    payment_id = f"pay_{uuid.uuid4().hex[:12]}"

    ORDERS_TABLE.put_item(Item={
        "orderId": order_id,
        "email": email,
        "items": body.get("items", [{"name": "EZIMarts Website Starter", "qty": 1}]),
        "amount": amount,
        "currency": body.get("currency", "USD"),
        "status": "checkout_started",
        "createdAt": now_iso(),
    })

    PAYMENTS_TABLE.put_item(Item={
        "paymentId": payment_id,
        "orderId": order_id,
        "email": email,
        "amount": amount,
        "currency": body.get("currency", "USD"),
        "provider": body.get("provider", "stripe"),
        "status": "checkout_started",
        "createdAt": now_iso(),
    })

    return response(200, {
        "message": "Checkout started. Replace checkoutUrl with real Stripe or PayPal hosted checkout session.",
        "orderId": order_id,
        "paymentId": payment_id,
        "checkoutUrl": "https://checkout.stripe.com/replace-with-real-session-url"
    })


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
        method = event.get("httpMethod", "")
        if method == "OPTIONS":
            return response(200, {"message": "CORS OK"})

        path = event.get("path", "")
        if method == "GET" and path.endswith("/status"):
            return site_status()

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

    except Exception as exc:
        print(f"ERROR: {exc}")
        return response(500, {"message": "Internal server error", "error": str(exc)})
