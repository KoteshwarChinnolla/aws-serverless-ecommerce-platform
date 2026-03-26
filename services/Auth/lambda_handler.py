import json
from service import (
    register, 
    login_password, 
    send_otp_verify, 
    request_otp,
    verify_otp_login, 
    refresh_token, 
    delete, 
    update,
    get_users_by_role, 
    logout,
    google_oauth_login,
    get_user_by_email
)
from address import add_address, delete_address, get_addresses, update_address

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
    
    # Safely parse body if it exists
    try:
        body = json.loads(event["body"]) if event.get("body") else {}
    except Exception:
        body = {}
        
    query_params = event.get("queryStringParameters") or {}
    
    # Normalize headers to lowercase for safer extraction (e.g., "Authorization" vs "authorization")
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}

    # Handle CORS preflight requests
    if http_method == "OPTIONS":
        return format_response({"statusCode": 200, "body": {"message": "CORS preflight successful"}})


    if http_method == "POST" and path == "/auth/register":
        return format_response(register(body))

    if http_method == "POST" and path == "/auth/login":
        return format_response(login_password(body))

    if http_method == "POST" and path == "/auth/otp/send":
        return format_response(send_otp_verify(body))

    if http_method == "POST" and path == "/auth/otp/request":
        return format_response(request_otp(body))

    if http_method == "POST" and path == "/auth/otp/verify":
        return format_response(verify_otp_login(body))

    if http_method == "POST" and path == "/auth/refresh":
        return format_response(refresh_token(body))

    if http_method == "POST" and path == "/auth/logout":
        return format_response(logout(headers))


    if http_method == "PUT" and path == "/auth/user":
        return format_response(update(body))
    
    if http_method == "GET" and path == "/auth/user":
        return format_response(get_user_by_email(query_params.get("email")))

    if http_method == "DELETE" and path == "/auth/user":
        return format_response(delete(body))

    if http_method == "GET" and path == "/auth/users":
        role = query_params.get("role", "USER")
        return format_response(get_users_by_role(role))
    
    if http_method == "POST" and path == "/auth/google":
        return format_response(google_oauth_login(body))
    
    if http_method == "POST" and path == "/user/address":
        return format_response(add_address(body))
    
    if http_method == "GET" and path == "/user/addresses":
        user_id = query_params.get("user_id")
        return format_response(get_addresses(user_id))
    
    if http_method == "DELETE" and path == "/user/address":
        user_id = query_params.get("user_id")
        address_id = query_params.get("address_id")
        return format_response(delete_address(user_id, address_id))
    
    if http_method == "PUT" and path == "/user/address":
        return format_response(update_address(body))

    return format_response({"statusCode": 404, "body": {"error": f"Route not found: {http_method} {path}"}})