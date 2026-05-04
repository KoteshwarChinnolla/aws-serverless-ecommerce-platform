import json
import jwt
import os
from datetime import datetime

JWT_SECRET = os.environ.get("JWT_SECRET", "CHANGE_ME_TO_STRONG_SECRET")
JWT_ALGO = os.environ.get("JWT_ALGO", "HS256")

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

def validate_admin(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get('role') == 'ADMIN':
            return {"statusCode": 200, "body": {"message": "Admin validated", "user": payload}}
        else:
            return {"statusCode": 403, "body": {"error": "Access denied. Admin role required."}}
    except jwt.ExpiredSignatureError:
        return {"statusCode": 401, "body": {"error": "Token expired"}}
    except jwt.InvalidTokenError:
        return {"statusCode": 401, "body": {"error": "Invalid token"}}

def lambda_handler(event, context):
    http_method = event.get("httpMethod")
    path = event.get("path")

    # Handle CORS preflight requests
    if http_method == "OPTIONS":
        return format_response({"statusCode": 200, "body": {"message": "CORS preflight successful"}})

    # Normalize headers to lowercase
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}

    if http_method == "POST" and path == "/admin/validate":
        auth_header = headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return format_response({"statusCode": 401, "body": {"error": "Authorization header missing or invalid"}})
        token = auth_header.split(" ")[1]
        return format_response(validate_admin(token))

    return format_response({"statusCode": 404, "body": {"error": f"Route not found: {http_method} {path}"}})