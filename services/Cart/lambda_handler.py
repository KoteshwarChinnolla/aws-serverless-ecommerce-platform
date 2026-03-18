import json
from service import (
    checkout_and_terminate_cart,
    create_or_update_cart,
    add_item_to_cart,
    get_active_cart_for_user,
    get_cart_with_filters,
    get_user_cart_history,
    update_item_quantity,
    remove_item_from_cart,
    clear_cart
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
        return format_response({"statusCode": 200, "body": {"message": "CORS successful"}})
    
    if path == "/cart":
        if http_method == "POST":
            return format_response(create_or_update_cart(body))
        elif http_method == "GET":
            cart_id = query_params.get("cart_id")
            return format_response(get_cart_with_filters(cart_id, query_params))
        elif http_method == "DELETE":
            cart_id = query_params.get("cart_id")
            return format_response(clear_cart(cart_id))


    if path == "/cart/item":
        if http_method == "POST":
            return format_response(add_item_to_cart(body.get("cart_id"), body))
        elif http_method == "PUT":
            return format_response(update_item_quantity(body.get("cart_id"), body.get("product_id"), int(body.get("quantity", 0))))
        elif http_method == "DELETE":
            return format_response(remove_item_from_cart(query_params.get("cart_id"), query_params.get("product_id")))
        
    if path == "/cart/user/history" and http_method == "GET":
        return format_response(get_user_cart_history(query_params.get("user_id")))
    
    if path == "/cart/user/active" and http_method == "GET":
        return format_response(get_active_cart_for_user(query_params.get("user_id")))
    
    if path == "/cart/checkout" and http_method == "POST":
        return format_response(checkout_and_terminate_cart(body))
    
    return format_response({"statusCode": 404, "body": {"error": "Route not found"}})