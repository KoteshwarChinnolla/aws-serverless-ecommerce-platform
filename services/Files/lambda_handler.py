import boto3
import base64
import uuid
import mimetypes
import json
from service import upload_url, get_presigned_url, delete_file
from banners import _response, create_banner, delete_banner, get_all_banners, get_banner, update_banner

def format_response(result):

    status_code = result.get('statusCode', 200)
    body = result.get('body', result)
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
    body = json.loads(event["body"]) if event.get("body") else {}
    query_params = event.get("queryStringParameters") or {}
    path_params = event.get("pathParameters") or {}
    headers = event.get("headers", {})

    if http_method == "OPTIONS":
        return {}

    if http_method == "POST" and path == "/file/applicant/store_file":
        return format_response(upload_url(body))

    if http_method == "GET" and path == "/file/applicant/get_file":
        return format_response(get_presigned_url(query_params.get("key")))

    if http_method == "DELETE" and path == "/file/applicant/delete_file":
        return format_response(delete_file(query_params.get("key")))

    if http_method == "OPTIONS":
        return _response({})

    if http_method == "POST" and path == "/banner/admin/banner":
        return create_banner(body)

    if http_method == "GET" and path == "/banner/admin/banners":
        return get_all_banners(query_params)

    if http_method == "PUT" and path == "/banner/admin/banner":
        return update_banner(query_params.get("banner_id"), body)

    if http_method == "GET" and path=="/banner/admin/banner":
        return get_banner(query_params.get("banner_id"))

    if http_method == "DELETE" and path=="/banner/admin/banner":
        return delete_banner(query_params.get("banner_id"))
    
    if http_method == "GET" and path=="/banner/public/banners":
        return get_all_banners(query_params)

    return _response({"error": "Route not found"}, 404)
