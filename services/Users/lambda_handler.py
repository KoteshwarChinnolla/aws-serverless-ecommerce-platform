import json
from service import (
    create_user_profile,
    update_user_profile,
    fetch_users_filters,
    get_user_address,
    fetch_user_by_id,
    fetch_user_by_email,
    fetch_all_users,
    delete_user
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


    if http_method == "POST" and path == "/user":
        return format_response(create_user_profile(body))

    if http_method == "PUT" and path == "/user":
        return format_response(update_user_profile(body))

    if http_method == "GET" and path == "/user":
        user_id = query_params.get("user_id")
        if not user_id:
            return format_response({"statusCode": 400, "body": {"error": "user_id query parameter is required"}})
        return format_response(fetch_user_by_id(user_id))

    if http_method == "DELETE" and path == "/user":
        user_id = query_params.get("user_id")
        if not user_id:
            return format_response({"statusCode": 400, "body": {"error": "user_id query parameter is required"}})
        return format_response(delete_user(user_id))

    if http_method == "POST" and path == "/user/search":
        return format_response(fetch_users_filters(body))


    if http_method == "GET" and path == "/user/address":
        user_id = query_params.get("user_id")
        if not user_id:
            return format_response({"statusCode": 400, "body": {"error": "user_id query parameter is required"}})
        return format_response(get_user_address(user_id))

    if http_method == "GET" and path == "/user/email":
        email = query_params.get("email")
        if not email:
            return format_response({"statusCode": 400, "body": {"error": "email query parameter is required"}})
        return format_response(fetch_user_by_email(email))


    if http_method == "GET" and path == "/user/all":
        return format_response(fetch_all_users())


    return format_response({"statusCode": 404, "body": {"error": f"Route not found: {http_method} {path}"}})