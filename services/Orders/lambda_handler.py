import json
from service import (
    create_order,
    get_order_by_id,
    get_orders_by_user,
    filter_orders,
    update_order_status
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


    if http_method == "GET" and path == "/orders":
        order_id = query_params.get("order_id")
        timestamp = query_params.get("timestamp")
        return format_response(get_order_by_id(order_id, timestamp))



    if http_method == "GET" and path == "/orders/user":
        user_id = query_params.get("user_id")
        return format_response(get_orders_by_user(user_id, limit=query_params.get("limit"), start_key=query_params.get("start_key")))


    if http_method == "GET" and path == "/orders/search":
        return format_response(filter_orders(query_params))


    if http_method == "PUT" and path == "/orders/status":
        return format_response(update_order_status(body))

    return format_response({"statusCode": 404, "body": {"error": f"Route not found: {http_method} {path}"}})