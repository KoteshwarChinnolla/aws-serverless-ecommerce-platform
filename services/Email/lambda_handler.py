import json
from service import (
    send_order_confirmation_email,
    send_order_status_email,
    send_order_cancelled_email,
    send_credentials_email,
    send_otp_email,
    send_invoice_email
)

def lambda_handler(event, context):
    print(event)
    if event.get("source") == "com.ecommerce.orders" and event.get("detail-type") == "OrderPlaced":
        return send_order_confirmation_email(event["detail"])

    http_method = event.get("httpMethod")
    path = event.get("path") 
    
    try:
        body = json.loads(event["body"]) if event.get("body") else {}
    except Exception:
        body = {}
        
    query_params = event.get("queryStringParameters") or {}
    path_params = event.get("pathParameters") or {}
    headers = event.get("headers", {})

    # Handle CORS preflight requests
    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
            "body": ""
        }
    

    if http_method == "POST" and path == "/email/user/otp":
        return send_otp_email(
            body.get("email"), 
            body.get("otp")
        )

    if http_method == "POST" and path == "/email/user/credentials":
        return send_credentials_email(
            body.get("name"), 
            body.get("email"), 
            body.get("password")
        )

    if http_method == "POST" and path == "/email/order/confirmation":
        return send_order_confirmation_email(
            body.get("name"), 
            body.get("email"), 
            body.get("order_id"), 
            body.get("product_summary")
        )

    if http_method == "POST" and path == "/email/order/status":
        return send_order_status_email(
            body.get("name"), 
            body.get("email"), 
            body.get("order_id"), 
            body.get("status_title"), 
            body.get("status_message")
        )

    if http_method == "POST" and path == "/email/order/cancel":
        return send_order_cancelled_email(
            body.get("name"), 
            body.get("email"), 
            body.get("order_id"), 
            body.get("reason", "Requested by user")
        )

    if http_method == "POST" and path == "/email/order/invoice":
        return send_invoice_email(
            body.get("name"), 
            body.get("email"), 
            body.get("order_id"), 
            body.get("file_name"), 
            body.get("base64_content")
        )

    return {
        "statusCode": 404,
        "body": json.dumps({"error": "Route not found"})
    }