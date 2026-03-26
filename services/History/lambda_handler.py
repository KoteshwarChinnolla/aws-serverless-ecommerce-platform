import json
from service import (
    log_order_created,
    get_order_timeline,
    update_order_stage,
    update_order_stage_bulk,
    fetch_order_flow,
    fetch_stage_ids_by_product,
    fetch_products_by_stage,
    fetch_products_by_user_id,
    get_all_addresses_by_user_id
)

def format_response(result):

    if isinstance(result, tuple) and len(result) == 2:
        body, status_code = result
    else:
        body = result
        status_code = 200

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT"
        },
        "body": json.dumps(body, default=str)
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
        return format_response(({"message": "CORS preflight successful"}, 200))


    if http_method == "POST" and path == "/tracking/order":
        return format_response(log_order_created(body))


    if http_method == "PUT" and path == "/tracking/stage":
        return format_response(update_order_stage(body))


    if http_method == "POST" and path == "/tracking/stage/bulk":
        return format_response(update_order_stage_bulk(body))


    if http_method == "GET" and path == "/tracking/timeline":
        user_id = query_params.get("user_id")
        if not user_id:
            return format_response(({"error": "user_id query parameter is required"}, 400))
        return format_response(get_order_timeline(user_id))


    if http_method == "GET" and path == "/tracking/flow":
        return format_response(fetch_order_flow(query_params))


    if http_method == "GET" and path == "/tracking/product/stages":
        return format_response(fetch_stage_ids_by_product(query_params))


    if http_method == "GET" and path == "/tracking/stage/products":
        return format_response(fetch_products_by_stage(query_params))


    if http_method == "GET" and path == "/tracking/user/products":
        return format_response(fetch_products_by_user_id(query_params))

    if http_method == "GET" and path == "/tracking/user/addresses":
        user_id = query_params.get("user_id")
        if not user_id:
            return format_response(({"error": "user_id query parameter is required"}, 400))
        return format_response(get_all_addresses_by_user_id(user_id))
    
    

    return format_response(({"error": f"Route not found: {http_method} {path}"}, 404))