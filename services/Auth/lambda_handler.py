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
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT,DELETE"
            },
            "body": ""
        }


    if http_method == "POST" and path == "/auth/register":
        return register(body)

    if http_method == "POST" and path == "/auth/login":
        return login_password(body)

    if http_method == "POST" and path == "/auth/otp/send":
        return send_otp_verify(body)

    if http_method == "POST" and path == "/auth/otp/request":
        return request_otp(body)

    if http_method == "POST" and path == "/auth/otp/verify":
        return verify_otp_login(body)

    if http_method == "POST" and path == "/auth/refresh":
        return refresh_token(body)

    if http_method == "POST" and path == "/auth/logout":
        return logout(headers)


    if http_method == "PUT" and path == "/auth/user":
        return update(body)
    
    if http_method == "GET" and path == "/auth/user":
        return get_user_by_email(query_params.get("email"))

    if http_method == "DELETE" and path == "/auth/user":
        return delete(body)

    if http_method == "GET" and path == "/auth/users":
        # Example usage: /auth/users?role=ADMIN
        role = query_params.get("role", "USER")
        return get_users_by_role(role)
    
    if http_method == "POST" and path == "/auth/google":
        return google_oauth_login(body)

    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": f"Route not found: {http_method} {path}"})
    }