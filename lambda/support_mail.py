import logging
import os
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr

import boto3


s3 = boto3.client("s3")
ses = boto3.client("sesv2")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAIL_BUCKET = os.environ["MAIL_BUCKET"]
MAIL_PREFIX = os.environ["MAIL_PREFIX"]
SUPPORT_ADDRESS = os.environ["SUPPORT_ADDRESS"]
SUPPORT_RECIPIENT = os.environ["SUPPORT_RECIPIENT"]
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024


def one_line(value):
    return " ".join(str(value or "").splitlines()).strip()


def forward_message(raw, key):
    original = BytesParser(policy=policy.default).parsebytes(raw)
    original_sender = one_line(original.get("From"))
    reply_to = parseaddr(one_line(original.get("Reply-To")) or original_sender)[1]
    subject = one_line(original.get("Subject")) or "(No subject)"
    body = original.get_body(preferencelist=("plain",))
    plain_text = body.get_content() if body else ""
    can_attach = len(raw) <= MAX_ATTACHMENT_BYTES

    forwarded = EmailMessage(policy=policy.SMTP)
    forwarded["From"] = SENDER_EMAIL
    forwarded["To"] = SUPPORT_RECIPIENT
    forwarded["Subject"] = f"Support: {subject[:200]}"
    if "@" in reply_to:
        forwarded["Reply-To"] = reply_to
    location = (
        "The original email is attached."
        if can_attach else f"The original email is available at s3://{MAIL_BUCKET}/{key}."
    )
    forwarded.set_content(
        f"From: {original_sender}\nTo: {SUPPORT_ADDRESS}\n"
        f"Subject: {subject}\n\n{str(plain_text)[:16000]}\n\n{location}"
    )
    if can_attach:
        forwarded.add_attachment(raw, maintype="application", subtype="octet-stream", filename="original.eml")

    ses.send_email(
        FromEmailAddress=SENDER_EMAIL,
        Destination={"ToAddresses": [SUPPORT_RECIPIENT]},
        Content={"Raw": {"Data": forwarded.as_bytes()}},
    )


def handler(event, context):
    for record in event["Records"]:
        receipt = record["ses"]["receipt"]
        mail = record["ses"]["mail"]
        if SUPPORT_ADDRESS not in [address.lower() for address in receipt["recipients"]]:
            continue
        if any(receipt.get(check, {}).get("status") != "PASS" for check in ("spamVerdict", "virusVerdict")):
            logger.info("Stored message %s without forwarding because a scan did not pass", mail["messageId"])
            continue
        key = MAIL_PREFIX + mail["messageId"]
        with s3.get_object(Bucket=MAIL_BUCKET, Key=key)["Body"] as stream:
            forward_message(stream.read(), key)
        logger.info("Forwarded support message %s", mail["messageId"])
