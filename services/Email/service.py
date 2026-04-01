import requests
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64

BREVO_URL = os.getenv("BREVO_URL", "https://api.brevo.com/v3/smtp/email")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")

DEFAULT_SENDER = {
    "name": "Ritual Elements",
    "email": "support@ritualelements.in"
}

track_order_link = os.getenv("TRACK_ORDER_LINK", "https://www.ritualelements.in/userorders")
LOGO_URL = os.getenv("LOGO_URL", "https://www.ritualelements.in/blacklogo.png")
SHOP_LINK = os.getenv("SHOP_LINK", "https://www.ritualelements.in")

def _brevo_headers():
    return {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }

# SENDER_EMAIL = "hr@anasol.co.in"
# APP_PASSWORD = "PHtE6r1bR+/sjGcp8EMD7fa5Fs+sZ9kp/OpjJQRC5dwUW6IFG00GrdwtxjLhoxsqUfIWRvWSnIM5ueuZseqFJGzrMz0fWGqyqK3sx/VYSPOZsbq6x00fsFsbdEDbVYHoddJu0yPWstzeNA=="
# # APP_PASSWORD = "eks9HmQ0HkVx"

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.zeptomail.in")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))


def send_email_smtp(payload):
    sender_email = SENDER_EMAIL
    subject = payload.get("subject", "Message from ACS")
    html_content = payload.get("htmlContent", "")
    to_emails = [recipient["email"] for recipient in payload.get("to", [])]

    if not to_emails:
        raise ValueError("At least one recipient email is required")

    attachments = payload.get("attachments", [])

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, APP_PASSWORD)

    sent_recipients = []
    failed_recipients = [] # New tracking array

    for email in to_emails:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = email
        msg["Subject"] = subject

        # HTML body
        msg.attach(MIMEText(html_content, "html"))

        # Attachments
        for attachment in attachments:
            file_name = attachment["fileName"]
            file_content_base64 = attachment["content"]
            file_bytes = base64.b64decode(file_content_base64)
            part = MIMEBase("application", "octet-stream")
            part.set_payload(file_bytes)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{file_name}"')
            msg.attach(part)

        # Try to send individually and catch immediate failures
        try:
            server.sendmail(sender_email, email, msg.as_string())
            sent_recipients.append(email)
        except Exception as e:
            print(f"Failed to send to {email}: {str(e)}")
            failed_recipients.append(email)

    server.quit()

    return {
        "status_code": 201,
        "sent": sent_recipients,
        "failed": failed_recipients
    }



def get_base_template(content):
    """Wraps specific email content in a consistent, premium Rituals-branded layout."""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <title>Ritual Elements</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #fdf8f3; font-family: Georgia, 'Times New Roman', serif;">

        <!-- Outer wrapper -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #fdf8f3; padding: 40px 16px;">
            <tr>
                <td align="center">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0"
                           style="max-width: 600px; width: 100%; background-color: #ffffff;
                                  border-radius: 2px;
                                  box-shadow: 0 2px 24px rgba(139, 90, 43, 0.08);">

                        <!-- Top accent bar -->
                        <tr>
                            <td style="background: linear-gradient(90deg, #c8a97e 0%, #e8c99a 50%, #c8a97e 100%); height: 4px; font-size: 0; line-height: 0;">&nbsp;</td>
                        </tr>

                        <!-- Header -->
                        <tr>
                            <td style="padding: 36px 40px 28px 40px; text-align: center; border-bottom: 1px solid #f0e8dc;">
                                <img src="{LOGO_URL}" alt="Ritual Elements" style="height: 60px; width: auto; display: block; margin: 0 auto 16px auto;">
                                <p style="margin: 0; font-family: Georgia, serif; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #c8a97e; font-weight: normal;">
                                    Mindful Living · Sacred Rituals
                                </p>
                            </td>
                        </tr>

                        <!-- Body Content -->
                        <tr>
                            <td style="padding: 44px 40px 36px 40px; color: #3d2b1f; line-height: 1.8; font-size: 15px;">
                                {content}
                            </td>
                        </tr>

                        <!-- Divider with ornament -->
                        <tr>
                            <td style="padding: 0 40px; text-align: center;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td style="border-top: 1px solid #f0e8dc; width: 45%;"></td>
                                        <td style="text-align: center; padding: 0 12px; color: #c8a97e; font-size: 18px; white-space: nowrap;">✦</td>
                                        <td style="border-top: 1px solid #f0e8dc; width: 45%;"></td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        <!-- Promotional Banner -->
                        <tr>
                            <td style="padding: 28px 40px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0"
                                       style="background: linear-gradient(135deg, #fdf1e4 0%, #fde8cc 100%);
                                              border-radius: 2px; border: 1px solid #e8d5b7;">
                                    <tr>
                                        <td style="padding: 20px 24px; text-align: center;">
                                            <p style="margin: 0 0 6px 0; font-family: Georgia, serif; font-size: 13px;
                                                       letter-spacing: 2px; text-transform: uppercase; color: #8b5a2b; font-weight: bold;">
                                                Shop with Ritual Elements
                                            </p>
                                            <p style="margin: 0 0 14px 0; font-size: 13px; color: #6b4226; line-height: 1.6;">
                                                Elevate your everyday. Discover sacred essentials crafted to bring<br>calm, clarity, and intention to your daily rituals.
                                            </p>
                                            <a href="{SHOP_LINK}"
                                               style="display: inline-block; background-color: #8b5a2b; color: #fdf8f3;
                                                      padding: 10px 24px; text-decoration: none; font-size: 12px;
                                                      letter-spacing: 2px; text-transform: uppercase; border-radius: 1px;
                                                      font-family: Georgia, serif;">
                                                Explore the Collection →
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #2e1f14; padding: 28px 40px; text-align: center; border-radius: 0 0 2px 2px;">
                                <p style="margin: 0 0 12px 0; font-family: Georgia, serif; font-size: 11px;
                                           letter-spacing: 3px; text-transform: uppercase; color: #c8a97e;">
                                    Ritual Elements
                                </p>
                                <p style="margin: 0 0 14px 0; font-size: 12px; color: #9e8070; line-height: 1.7;">
                                    Improve your well-being · Transform your space · Live with intention
                                </p>
                                <a href="{track_order_link}"
                                   style="color: #e8c99a; text-decoration: none; font-size: 12px;
                                          letter-spacing: 1px; border-bottom: 1px solid #c8a97e; padding-bottom: 1px;">
                                    Track Your Order
                                </a>
                                &nbsp;&nbsp;·&nbsp;&nbsp;
                                <a href="{SHOP_LINK}"
                                   style="color: #e8c99a; text-decoration: none; font-size: 12px;
                                          letter-spacing: 1px; border-bottom: 1px solid #c8a97e; padding-bottom: 1px;">
                                    Visit Our Store
                                </a>
                                <p style="margin: 16px 0 0 0; font-size: 11px; color: #6b5045;">
                                    &copy; 2026 Ritual Elements. All rights reserved.
                                </p>
                            </td>
                        </tr>

                        <!-- Bottom accent bar -->
                        <tr>
                            <td style="background: linear-gradient(90deg, #c8a97e 0%, #e8c99a 50%, #c8a97e 100%); height: 3px; font-size: 0; line-height: 0;">&nbsp;</td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>

    </body>
    </html>
    """


# --- CORE SENDING FUNCTIONS ---

def send_email_with_attachment(body):
    required = ["to_email", "html_content", "attachment_name", "attachment_base64"]
    for f in required:
        if not body.get(f):
            return {"error": f"{f} is required"}, 400

    payload = {
        "sender": body.get("sender", DEFAULT_SENDER),
        "to": [{"email": body["to_email"]}],
        "subject": body.get("subject", "A message from Ritual Elements"),
        "htmlContent": body["html_content"],
        "attachment": [
            {
                "name": body["attachment_name"],
                "content": body["attachment_base64"]
            }
        ]
    }

    # r = requests.post(BREVO_URL, headers=_brevo_headers(), json=payload)
    r = send_email_smtp(payload)
    if r.status_code == 201:
        return {"success": True}, 200
    return {"success": False, "error": r.text}, r.status_code

def send_single_email(body):
    required = ["to_email", "html_content"]
    for f in required:
        if not body.get(f):
            return {"error": f"{f} is required"}, 400

    payload = {
        "sender": body.get("sender", DEFAULT_SENDER),
        "to": [{"email": body["to_email"]}],
        "subject": body.get("subject", "A message from Ritual Elements"),
        "htmlContent": body["html_content"]
    }

    # r = requests.post(BREVO_URL, headers=_brevo_headers(), json=payload)
    r = send_email_smtp(payload)
    if r.status_code == 201:
        return {"success": True}, 200
    return {"success": False, "error": r.text}, r.status_code


# --- E-COMMERCE EMAIL TEMPLATES ---

def send_order_confirmation_email(event_detail):
    print("Preparing order confirmation email with details:", event_detail)
    name = event_detail.get("user_name", "Valued Customer")
    email = event_detail.get("user_email")
    order_id = event_detail.get("order_id")

    product_rows = ""
    for item in event_detail.get("line_items", []):
        product_rows += f"""
        <tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0e8dc; color: #3d2b1f; font-size: 14px;">
                {item.get('quantity', 1)} &times; {item.get('name', 'Product')}
            </td>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0e8dc; color: #8b5a2b;
                       font-size: 14px; text-align: right; font-weight: bold;">
                ₹{item.get('price', 0):.2f}
            </td>
        </tr>
        """
    extra_amount = float(event_detail.get("payment_details", {}).get("extra", 0)) if event_detail.get("cash_on_delivery") else 0
    if event_detail.get("cash_on_delivery"):
        product_rows += f"""
        <tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0e8dc; color: #3d2b1f; font-size: 14px;">
                Cash on Delivery Fee
            </td>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0e8dc; color: #8b5a2b;
                       font-size: 14px; text-align: right; font-weight: bold;">
                ₹{extra_amount:.2f}
            </td>
        </tr>
        """ 


    total_amount = event_detail.get("total_amount", 0)
    shipping_address = event_detail.get("shipping_address", {})

    shipping_block = ""
    if shipping_address:
        shipping_block = f"""
        <div style="margin-top: 24px; padding: 16px 20px; background-color: #fdf8f3;
                    border: 1px solid #f0e8dc; border-radius: 1px;">
            <p style="margin: 0 0 8px 0; font-size: 11px; letter-spacing: 2px;
                       text-transform: uppercase; color: #c8a97e; font-weight: bold;">
                Shipping Address
            </p>
            <p style="margin: 0; font-size: 14px; color: #5a3e2b; line-height: 1.7;">
                {shipping_address.get('name', '')}<br>
                {shipping_address.get('line1', '')} {shipping_address.get('street', '')}<br>
                {shipping_address.get('city', '')}, {shipping_address.get('state', '')} {shipping_address.get('zip', '')}<br>
                {shipping_address.get('country', '')}
            </p>
        </div>
        """

    inner_content = f"""
        <p style="margin: 0 0 4px 0; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #c8a97e;">
            Thank you for your order
        </p>
        <h2 style="margin: 0 0 20px 0; font-family: Georgia, serif; font-size: 26px;
                   color: #2e1f14; font-weight: normal; letter-spacing: 0.5px;">
            Order Confirmed ✦
        </h2>

        <p style="margin: 0 0 20px 0; color: #5a3e2b;">
            Dear {name}, your sacred essentials are on their way to you. We've received your order
            <strong style="color: #8b5a2b;">#{order_id}</strong> and our team is carefully preparing your items with intention and care.
        </p>

        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 24px 0;">
            <tr>
                <td style="padding: 8px 0; border-bottom: 2px solid #c8a97e;">
                    <span style="font-size: 11px; letter-spacing: 2px; text-transform: uppercase;
                                  color: #8b5a2b; font-weight: bold;">Item</span>
                </td>
                <td style="padding: 8px 0; border-bottom: 2px solid #c8a97e; text-align: right;">
                    <span style="font-size: 11px; letter-spacing: 2px; text-transform: uppercase;
                                  color: #8b5a2b; font-weight: bold;">Price</span>
                </td>
            </tr>
            {product_rows}
            <tr>
                <td style="padding: 14px 0 4px 0; font-size: 15px; font-weight: bold; color: #2e1f14;">
                    Total
                </td>
                <td style="padding: 14px 0 4px 0; text-align: right; font-size: 17px;
                            font-weight: bold; color: #8b5a2b;">
                    ₹{total_amount:.2f}
                </td>
            </tr>
        </table>

        {shipping_block}

        <p style="margin: 24px 0 8px 0; color: #5a3e2b; font-size: 14px;">
            You'll receive another notification once your order has been dispatched. In the meantime, shop
            with Ritual Elements and improve your everyday rituals — explore our full collection of mindful essentials.
        </p>

        <div style="text-align: center; margin: 32px 0;">
            <a href="{track_order_link}"
               style="display: inline-block; background-color: #8b5a2b; color: #fdf8f3;
                      padding: 14px 32px; text-decoration: none; font-size: 12px;
                      letter-spacing: 2px; text-transform: uppercase; border-radius: 1px;
                      font-family: Georgia, serif;">
                View Order Details
            </a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #5a3e2b;">
            With gratitude,<br>
            <strong style="color: #2e1f14;">The Ritual Elements Team</strong>
        </p>
    """

    print("Final email content prepared, sending email...")
    return send_single_email({
        "to_email": email,
        "subject": f"Your Ritual Elements Order is Confirmed ✦ #{order_id}",
        "html_content": get_base_template(inner_content)
    })


def send_order_status_email(name, email, order_id, status_title, status_message):
    """
    Use this for dynamically updating the user:
    e.g. status_title="Order Dispatched", status_message="Your package has been handed over to our delivery partner."
    """
    inner_content = f"""
        <p style="margin: 0 0 4px 0; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #c8a97e;">
            Order Update · #{order_id}
        </p>
        <h2 style="margin: 0 0 20px 0; font-family: Georgia, serif; font-size: 26px;
                   color: #2e1f14; font-weight: normal;">
            {status_title}
        </h2>

        <p style="margin: 0 0 20px 0; color: #5a3e2b;">
            Dear {name}, we have an update on your Ritual Elements order.
        </p>

        <div style="background: linear-gradient(135deg, #fdf8f3 0%, #fdf1e4 100%);
                    border-left: 3px solid #c8a97e; padding: 18px 20px; margin: 20px 0;
                    border-radius: 0 2px 2px 0;">
            <p style="margin: 0 0 4px 0; font-size: 11px; letter-spacing: 2px;
                       text-transform: uppercase; color: #c8a97e;">Current Status</p>
            <p style="margin: 0; color: #3d2b1f; font-size: 15px; line-height: 1.7;">
                {status_message}
            </p>
        </div>

        <p style="margin: 20px 0; color: #5a3e2b; font-size: 14px;">
            Track your delivery in real time by visiting your account. Shop with Ritual Elements
            and discover new ways to improve your daily practice — your next favourite ritual awaits.
        </p>

        <div style="text-align: center; margin: 32px 0;">
            <a href="{track_order_link}"
               style="display: inline-block; background-color: #8b5a2b; color: #fdf8f3;
                      padding: 14px 32px; text-decoration: none; font-size: 12px;
                      letter-spacing: 2px; text-transform: uppercase; border-radius: 1px;
                      font-family: Georgia, serif;">
                Track Delivery
            </a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #5a3e2b;">
            Thank you for your patience,<br>
            <strong style="color: #2e1f14;">The Ritual Elements Fulfilment Team</strong>
        </p>
    """

    return send_single_email({
        "to_email": email,
        "subject": f"Ritual Elements: {status_title} · Order #{order_id}",
        "html_content": get_base_template(inner_content)
    })


def send_order_cancelled_email(name, email, order_id, reason="Requested by customer"):
    inner_content = f"""
        <p style="margin: 0 0 4px 0; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #b07070;">
            Order Cancellation · #{order_id}
        </p>
        <h2 style="margin: 0 0 20px 0; font-family: Georgia, serif; font-size: 26px;
                   color: #2e1f14; font-weight: normal;">
            Your Order Has Been Cancelled
        </h2>

        <p style="margin: 0 0 16px 0; color: #5a3e2b;">
            Dear {name}, we're sorry to see your order go. Your order
            <strong style="color: #8b5a2b;">#{order_id}</strong> has been successfully cancelled.
        </p>

        <div style="background-color: #fff9f9; border: 1px solid #f0d8d8;
                    padding: 16px 20px; border-radius: 1px; margin: 20px 0;">
            <p style="margin: 0 0 4px 0; font-size: 11px; letter-spacing: 2px;
                       text-transform: uppercase; color: #b07070;">Cancellation Reason</p>
            <p style="margin: 0; font-size: 14px; color: #3d2b1f;">{reason}</p>
        </div>

        <p style="margin: 16px 0; color: #5a3e2b; font-size: 14px;">
            If a payment was made, your refund has been initiated and will reflect in your original
            payment method within <strong>5–7 business days</strong>.
        </p>

        <p style="margin: 16px 0; color: #5a3e2b; font-size: 14px;">
            We'd love the opportunity to serve you again. Shop with Ritual Elements and improve
            your daily well-being — whenever you're ready, your ritual awaits.
        </p>

        <div style="text-align: center; margin: 32px 0;">
            <a href="{SHOP_LINK}"
               style="display: inline-block; background-color: #8b5a2b; color: #fdf8f3;
                      padding: 14px 32px; text-decoration: none; font-size: 12px;
                      letter-spacing: 2px; text-transform: uppercase; border-radius: 1px;
                      font-family: Georgia, serif;">
                Continue Shopping
            </a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #5a3e2b;">
            We hope to serve you again soon,<br>
            <strong style="color: #2e1f14;">The Ritual Elements Support Team</strong>
        </p>
    """

    return send_single_email({
        "to_email": email,
        "subject": f"Ritual Elements · Order Cancelled #{order_id}",
        "html_content": get_base_template(inner_content)
    })


def send_credentials_email(name, email, password):
    inner_content = f"""
        <p style="margin: 0 0 4px 0; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #c8a97e;">
            Welcome to the Community
        </p>
        <h2 style="margin: 0 0 20px 0; font-family: Georgia, serif; font-size: 26px;
                   color: #2e1f14; font-weight: normal;">
            Your Account Is Ready ✦
        </h2>

        <p style="margin: 0 0 16px 0; color: #5a3e2b;">
            Dear {name}, welcome to Ritual Elements — your destination for sacred essentials
            that bring calm, clarity, and intention to everyday life.
        </p>

        <p style="margin: 0 0 20px 0; color: #5a3e2b; font-size: 14px;">
            An account has been created so you can easily track your orders and improve your
            shopping experience. Here are your login credentials:
        </p>

        <div style="background: linear-gradient(135deg, #fdf8f3 0%, #fdf1e4 100%);
                    border: 1px solid #e8d5b7; padding: 22px 24px;
                    border-radius: 1px; margin: 24px 0;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    <td style="padding: 6px 0;">
                        <span style="font-size: 11px; letter-spacing: 2px; text-transform: uppercase;
                                      color: #c8a97e; display: block; margin-bottom: 2px;">Email</span>
                        <span style="font-size: 15px; color: #2e1f14;">{email}</span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 14px 0 6px 0; border-top: 1px solid #f0e8dc; margin-top: 12px;">
                        <span style="font-size: 11px; letter-spacing: 2px; text-transform: uppercase;
                                      color: #c8a97e; display: block; margin-bottom: 2px; margin-top: 10px;">Password</span>
                        <span style="font-size: 15px; color: #2e1f14; font-family: 'Courier New', monospace;
                                      background-color: #fff; padding: 4px 10px; border: 1px dashed #e8d5b7;
                                      border-radius: 1px; display: inline-block; letter-spacing: 1px;">{password}</span>
                    </td>
                </tr>
            </table>
        </div>

        <p style="margin: 0 0 24px 0; color: #7a5c44; font-size: 13px;">
            🔒 For your security, we recommend changing your password after your first login.
        </p>

        <div style="text-align: center; margin: 32px 0;">
            <a href="{SHOP_LINK}"
               style="display: inline-block; background-color: #8b5a2b; color: #fdf8f3;
                      padding: 14px 32px; text-decoration: none; font-size: 12px;
                      letter-spacing: 2px; text-transform: uppercase; border-radius: 1px;
                      font-family: Georgia, serif;">
                Login &amp; Start Shopping
            </a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #5a3e2b;">
            With warmth,<br>
            <strong style="color: #2e1f14;">The Ritual Elements Team</strong>
        </p>
    """

    return send_single_email({
        "to_email": email,
        "subject": "Welcome to Ritual Elements · Your Account is Ready",
        "html_content": get_base_template(inner_content)
    })


def send_otp_email(email, otp):
    inner_content = f"""
        <p style="margin: 0 0 4px 0; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #c8a97e;">
            Security Verification
        </p>
        <h2 style="margin: 0 0 20px 0; font-family: Georgia, serif; font-size: 26px;
                   color: #2e1f14; font-weight: normal;">
            Your Login Code
        </h2>

        <p style="margin: 0 0 16px 0; color: #5a3e2b;">
            Hello,
        </p>
        <p style="margin: 0 0 24px 0; color: #5a3e2b; font-size: 14px;">
            Use the one-time verification code below to securely access your Ritual Elements account.
            This code is valid for <strong>10 minutes</strong>.
        </p>

        <div style="text-align: center; margin: 36px 0;">
            <div style="display: inline-block; background: linear-gradient(135deg, #fdf1e4 0%, #fde8cc 100%);
                        border: 2px dashed #c8a97e; padding: 20px 40px; border-radius: 2px;">
                <p style="margin: 0 0 6px 0; font-size: 11px; letter-spacing: 2px;
                           text-transform: uppercase; color: #c8a97e;">Verification Code</p>
                <span style="font-size: 40px; font-weight: bold; letter-spacing: 10px;
                              color: #8b5a2b; font-family: 'Courier New', monospace;
                              display: block;">{otp}</span>
            </div>
        </div>

        <p style="margin: 0 0 8px 0; color: #7a5c44; font-size: 13px; text-align: center;">
            ⏱ Expires in 10 minutes
        </p>

        <p style="margin: 20px 0 0 0; color: #9e8070; font-size: 13px; text-align: center;">
            If you did not request this code, please disregard this email and ensure your account is secure.
        </p>

        <p style="margin: 28px 0 0 0; font-size: 14px; color: #5a3e2b;">
            Best regards,<br>
            <strong style="color: #2e1f14;">The Ritual Elements Security Team</strong>
        </p>
    """

    return send_single_email({
        "to_email": email,
        "subject": "Ritual Elements · Your Login Verification Code",
        "html_content": get_base_template(inner_content)
    })


def send_invoice_email(name, email, order_id, file_name, base64_content):
    """
    Sends an email containing the order invoice as an attachment.
    """
    inner_content = f"""
        <p style="margin: 0 0 4px 0; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #c8a97e;">
            Billing Document
        </p>
        <h2 style="margin: 0 0 20px 0; font-family: Georgia, serif; font-size: 26px;
                   color: #2e1f14; font-weight: normal;">
            Your Invoice is Attached ✦
        </h2>

        <p style="margin: 0 0 16px 0; color: #5a3e2b;">
            Dear {name}, thank you for choosing Ritual Elements. Please find the official invoice
            for your order <strong style="color: #8b5a2b;">#{order_id}</strong> attached to this email.
        </p>

        <p style="margin: 0 0 24px 0; color: #5a3e2b; font-size: 14px;">
            We hope your new essentials bring a meaningful upgrade to your daily rituals and
            improve your overall sense of well-being.
        </p>

        <div style="background: linear-gradient(135deg, #fdf8f3 0%, #fdf1e4 100%);
                    border-left: 3px solid #c8a97e; padding: 18px 20px; margin: 24px 0;
                    border-radius: 0 2px 2px 0;">
            <p style="margin: 0 0 4px 0; font-size: 11px; letter-spacing: 2px;
                       text-transform: uppercase; color: #c8a97e;">Attached Document</p>
            <p style="margin: 0; font-size: 15px; color: #2e1f14;">
                📎 &nbsp;<strong>{file_name}</strong>
            </p>
        </div>

        <p style="margin: 0 0 24px 0; color: #7a5c44; font-size: 13px;">
            If you notice any discrepancies or have questions about your invoice, our support
            team is always happy to help.
        </p>

        <div style="text-align: center; margin: 32px 0;">
            <a href="{track_order_link}"
               style="display: inline-block; background-color: #8b5a2b; color: #fdf8f3;
                      padding: 14px 32px; text-decoration: none; font-size: 12px;
                      letter-spacing: 2px; text-transform: uppercase; border-radius: 1px;
                      font-family: Georgia, serif;">
                Track Your Order
            </a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #5a3e2b;">
            With gratitude,<br>
            <strong style="color: #2e1f14;">The Ritual Elements Billing Team</strong>
        </p>
    """

    return send_email_with_attachment({
        "to_email": email,
        "subject": f"Ritual Elements · Invoice for Order #{order_id}",
        "html_content": get_base_template(inner_content),
        "attachment_name": file_name,
        "attachment_base64": base64_content
    })