import json
from service import (
    create_order,
    update_order,
    delete_order,
    get_order_by_id,
    get_orders_by_user,
    filter_orders,
    get_all_orders_short
)

def format_response(result):
    status_code = result.get('statusCode', 200)
    body = result.get('body', {})
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT,DELETE"
        },
        "body": json.dumps(body, default=str) if not isinstance(body, str) else body
    }

def lambda_handler(event, context):
    http_method = event.get("httpMethod")
    path = event.get("path") 
    
    try:
        body = json.loads(event["body"]) if event.get("body") else {}
    except Exception:
        body = {}
        
    query_params = event.get("queryStringParameters") or {}


    if http_method == "OPTIONS":
        return format_response({"statusCode": 200, "body": {"message": "CORS preflight successful"}})

    if http_method == "POST" and path == "/orders":
        return format_response(create_order(body))


    if http_method == "PUT" and path == "/orders":
        return format_response(update_order(body))


    if http_method == "GET" and path == "/orders":
        order_id = query_params.get("order_id")
        timestamp = query_params.get("timestamp")
        return format_response(get_order_by_id(order_id, timestamp))


    if http_method == "DELETE" and path == "/orders":
        order_id = query_params.get("order_id")
        timestamp = query_params.get("timestamp")
        return format_response(delete_order(order_id, timestamp))


    if http_method == "GET" and path == "/orders/user":
        user_id = query_params.get("user_id")
        # Optional: ?short=true to get summarized versions
        is_short = query_params.get("short", "false").lower() == "true"
        return format_response(get_orders_by_user(user_id, short=is_short))


    if http_method == "POST" and path == "/orders/search":
        return format_response(filter_orders(body))

    if http_method == "GET" and path == "/orders/all/short":
        return format_response(get_all_orders_short())


    return format_response({"statusCode": 404, "body": {"error": f"Route not found: {http_method} {path}"}})