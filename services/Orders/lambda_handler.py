import json
from service import (
    get_dashboard_summary,
    init_checkout,
    verify_and_place_order,
    get_user_orders,
    admin_search_orders,
    admin_update_status,
    get_order_by_id,
    cancel_order
)
import os

API_KEY = os.getenv("RAZORPAY_API_KEY")

def format_response(result):
    return {
        "statusCode": result.get('statusCode', 200),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT,DELETE"
        },
        "body": json.dumps(result.get('body', {}), default=str)
    }

def lambda_handler(event, context):
    print(event)
    # Handle EventBridge events
    if event.get("source") == "com.ecommerce.orders" and event.get("detail-type") == "OrderPlaced":
        print("Received OrderPlaced event:", event)
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "OrderPlaced event received"})
        }

    http_method = event.get("httpMethod")
    path = event.get("path") 
    
    try:
        body = json.loads(event["body"]) if event.get("body") else {}
    except Exception:
        body = {}
        
    query_params = event.get("queryStringParameters") or {}

    if http_method == "OPTIONS":
        return format_response({"statusCode": 200, "body": {"message": "CORS preflight successful"}})

    if path.startswith("/orders/user"):
        
        user_id = body.get("user_id") or query_params.get("user_id")

        if http_method == "POST" and path == "/orders/user/checkout":
            return format_response(init_checkout(body, user_id))
            
        if http_method == "POST" and path == "/orders/user/verify":
            return format_response(verify_and_place_order(body, user_id))

        if http_method == "GET" and path == "/orders/user":
            return format_response(get_user_orders(user_id, limit=query_params.get("limit"), start_key=query_params.get("start_key")))

        if http_method == "PUT" and path == "/orders/user/cancel":
            return format_response(cancel_order(body))

    if path.startswith("/orders/admin"):
        if http_method == "GET" and path == "/orders/admin/search":
            return format_response(admin_search_orders(query_params))

        if http_method == "GET" and path == "/orders/admin/details":
            return format_response(get_order_by_id(query_params.get("order_id"), query_params.get("timestamp")))

        if http_method == "PUT" and path == "/orders/admin/status":
            return format_response(admin_update_status(body))

        if http_method == "PUT" and path == "/orders/admin/cancel":
            return format_response(cancel_order(body))
        
        if http_method == "GET" and path == "/orders/admin":
            return format_response(get_dashboard_summary())

    return format_response({"statusCode": 404, "body": {"error": f"Route not found: {http_method} {path}"}})

