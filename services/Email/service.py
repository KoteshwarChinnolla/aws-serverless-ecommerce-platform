import requests
import os

BREVO_URL = os.getenv("BREVO_URL", "https://api.brevo.com/v3/smtp/email")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")

DEFAULT_SENDER = {
    "name": "ACS Support Team",
    "email": "kohlicriss@gmail.com"
}

track_order_link = os.getenv("TRACK_ORDER_LINK", "https://www.ritualelements.in/track-order")
LOGO_URL = os.getenv("LOGO_URL", "https://www.ritualelements.in/ritual-logo.png")

def _brevo_headers():
    return {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }

def get_base_template(content):
    """Wraps specific email content in a consistent, professional branded layout."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f4f7fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f7fa; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="100%" max-width="600px" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); max-width: 600px; width: 100%;">
                        <tr>
                            <td style="padding: 30px; text-align: center; border-bottom: 1px solid #f0f0f0;">
                                <img src="{LOGO_URL}" alt="ACS Logo" style="height: 55px; width: auto; display: block; margin: 0 auto;">
                            </td>
                        </tr>
                        
                        <tr>
                            <td style="padding: 40px 30px; color: #333333; line-height: 1.6; font-size: 16px;">
                                {content}
                            </td>
                        </tr>
                        
                        <tr>
                            <td style="background-color: #f8fafc; padding: 25px 30px; text-align: center; font-size: 13px; color: #888888; border-top: 1px solid #f0f0f0;">
                                &copy; 2026 ACS. All rights reserved.<br>
                                <a href="{track_order_link}" style="color: #ff6b00; text-decoration: none; font-weight: bold;">Track Your Order</a>
                            </td>
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
        "subject": body.get("subject", "Message from ACS"),
        "htmlContent": body["html_content"],
        "attachment": [
            {
                "name": body["attachment_name"],
                "content": body["attachment_base64"]
            }
        ]
    }

    r = requests.post(BREVO_URL, headers=_brevo_headers(), json=payload)
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
        "subject": body.get("subject", "Message from ACS"),
        "htmlContent": body["html_content"]
    }

    r = requests.post(BREVO_URL, headers=_brevo_headers(), json=payload)
    if r.status_code == 201:
        return {"success": True}, 200
    return {"success": False, "error": r.text}, r.status_code


# --- E-COMMERCE EMAIL TEMPLATES ---

def send_order_confirmation_email(event_detail):
    print("Preparing order confirmation email with details:", event_detail)
    name = event_detail.get("user_name", "Customer")
    email = event_detail.get("user_email")
    order_id = event_detail.get("order_id")
    product_summary = ""
    for item in event_detail.get("line_items", []):
        product_summary += f"{item.get('quantity', 1)} x {item.get('name', 'Product')} (${item.get('price', 0):.2f})<br>"
    total_amount = event_detail.get("total_amount", 0)
    shipment_address = event_detail.get("shipment_address", {})
    if shipment_address:
        product_summary += f"<br><strong>Shipping To:</strong><br>{shipment_address.get('name', '')}<br>{shipment_address.get('email', '')}<br>{shipment_address.get('line1', '')}<br>{shipment_address.get('street', '')}<br>{shipment_address.get('city', '')}, {shipment_address.get('state', '')} {shipment_address.get('zip', '')}<br>{shipment_address.get('country', '')}"

    inner_content = f"""
        <h2 style="color: #1e293b; margin-top: 0;">Order Received!</h2>
        <p>Hi {name},</p>
        <p>Thank you for shopping with ACS! We have successfully received your order <strong>#{order_id}</strong>.</p>
        <p><strong>Order Summary:</strong> {product_summary}</p>
        <p><strong>Total Amount:</strong> ${total_amount:.2f}</p>
        <p>Our team is currently preparing your items. You will receive another notification once your order has been dispatched.</p>
        
        <div style="text-align: center; margin: 35px 0;">
            <a href="{track_order_link}" style="background-color: #ff6b00; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">View Order Details</a>
        </div>
        
        <p style="margin-bottom: 0;">Best regards,<br><strong>The ACS Support Team</strong></p>
    """
    print("Final email content prepared, sending email...")
    return send_single_email({
        "to_email": email,
        "subject": f"ACS – Order Confirmation #{order_id}",
        "html_content": get_base_template(inner_content)
    })

def send_order_status_email(name, email, order_id, status_title, status_message):
    """
    Use this for dynamically updating the user: 
    e.g. status_title="Order Dispatched", status_message="Your package has been handed over to our delivery partner."
    """
    inner_content = f"""
        <h2 style="color: #1e293b; margin-top: 0;">{status_title}</h2>
        <p>Hi {name},</p>
        <p>We have an update regarding your order <strong>#{order_id}</strong>:</p>
        <div style="background-color: #f8fafc; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0;">
            <p style="margin: 0; color: #475569; font-size: 16px;">
                <strong>Status:</strong> {status_message}
            </p>
        </div>
        <p>You can track the live status of your delivery by logging into your account.</p>
        
        <div style="text-align: center; margin: 35px 0;">
            <a href="{track_order_link}" style="background-color: #ff6b00; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Track Delivery</a>
        </div>
        
        <p style="margin-bottom: 0;">Thank you for your patience,<br><strong>The ACS Fulfillment Team</strong></p>
    """

    return send_single_email({
        "to_email": email,
        "subject": f"ACS Update: {status_title} (Order #{order_id})",
        "html_content": get_base_template(inner_content)
    })

def send_order_cancelled_email(name, email, order_id, reason="Requested by user"):
    inner_content = f"""
        <h2 style="color: #ef4444; margin-top: 0;">Order Cancelled</h2>
        <p>Hi {name},</p>
        <p>Your order <strong>#{order_id}</strong> has been cancelled.</p>
        <p><strong>Reason:</strong> {reason}</p>
        <p>If you have already paid for this order, the refund process has been initiated and will reflect in your original payment method within 5-7 business days.</p>
        
        <p style="margin-bottom: 0;">We hope to serve you again soon,<br><strong>The ACS Support Team</strong></p>
    """

    return send_single_email({
        "to_email": email,
        "subject": f"ACS – Order Cancelled #{order_id}",
        "html_content": get_base_template(inner_content)
    })

def send_credentials_email(name, email, password):
    inner_content = f"""
        <h2 style="color: #1e293b; margin-top: 0;">Welcome to ACS Store!</h2>
        <p>Hi {name},</p>
        <p>An account has been created for you to easily track your orders and manage your purchases. Use the secure credentials below to log in.</p>
        
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 20px; border-radius: 8px; margin: 25px 0;">
            <p style="margin: 0 0 10px 0; font-size: 15px;"><strong>Email:</strong> <span style="color: #475569;">{email}</span></p>
            <p style="margin: 0; font-size: 15px;"><strong>Password:</strong> <span style="color: #475569;">{password}</span></p>
        </div>
        
        <div style="text-align: center; margin: 35px 0;">
            <a href="{track_order_link}" style="background-color: #6366f1; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Login to Store</a>
        </div>
        
        <p style="margin-bottom: 0;">Best regards,<br><strong>The ACS Team</strong></p>
    """
    
    return send_single_email({
        "to_email": email,
        "subject": "ACS – Your Account Credentials",
        "html_content": get_base_template(inner_content)
    })

def send_otp_email(email, otp):
    inner_content = f"""
        <h2 style="color: #1e293b; margin-top: 0;">Verify Your Login</h2>
        <p>Hello,</p>
        <p>Please use the verification code below to securely log into your ACS account. This code will expire in <strong>10 minutes</strong>.</p>
        
        <div style="text-align: center; margin: 40px 0;">
            <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #ff6b00; background-color: #fff7ed; padding: 15px 30px; border-radius: 10px; border: 2px dashed #fed7aa; display: inline-block;">{otp}</span>
        </div>
        
        <p style="color: #64748b; font-size: 14px;">If you did not request this code, please secure your account immediately.</p>
        <p style="margin-bottom: 0;">Best regards,<br><strong>The ACS Security Team</strong></p>
    """
    
    return send_single_email({
        "to_email": email,
        "subject": "ACS – Login Verification Code",
        "html_content": get_base_template(inner_content)
    })

def send_invoice_email(name, email, order_id, file_name, base64_content):
    """
    Sends an email containing the order invoice as an attachment.
    """
    inner_content = f"""
        <h2 style="color: #1e293b; margin-top: 0;">Your Order Invoice</h2>
        <p>Hi {name},</p>
        <p>Thank you for your recent purchase! Please find the official invoice for your order <strong>#{order_id}</strong> attached to this email.</p>
        <p>If you notice any discrepancies or have questions regarding your bill, please reach out to our support team.</p>
        
        <div style="background-color: #f8fafc; border-left: 4px solid #ff6b00; padding: 15px; margin: 30px 0; border-radius: 0 8px 8px 0;">
            <p style="margin: 0; color: #475569; font-size: 15px; display: flex; align-items: center;">
                <strong style="color: #1e293b; margin-right: 8px;">📎 Attached File:</strong> {file_name}
            </p>
        </div>
        
        <p style="margin-bottom: 0;">Best regards,<br><strong>The ACS Billing Team</strong></p>
    """
    
    return send_email_with_attachment({
        "to_email": email,
        "subject": f"ACS – Invoice for Order #{order_id}",
        "html_content": get_base_template(inner_content),
        "attachment_name": file_name,
        "attachment_base64": base64_content
    })