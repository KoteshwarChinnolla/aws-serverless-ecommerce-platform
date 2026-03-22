import json


from products_service import (
    create_product,
    update_product,
    search_products,
    delete_product
)
from variant import (
    add_variant, 
    update_variant,
    get_product_with_short_variants, 
    get_full_variant,
    delete_variant
)

# Import Category Services
from category_service import (
    store_category_metadata,
    update_category_metadata,
    delete_category_metadata,
    get_products_by_category,
    find_unique_categories,
    get_all_categories_with_metadata
)

# Import Request Services
from requests_service import (
    request_product,
    get_requested_projects_by_user,
    search_requested_projects,
    update_requested_project,
    approve_requested_project,
    delete_requested_project
)



def format_response(result):
    """Helper to standardize API Gateway responses."""
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

    if http_method == "POST" and path == "/products/admin":
        return format_response(create_product(body))
    if http_method == "PUT" and path == "/products/admin":
        return format_response(update_product(body))
    if http_method == "DELETE" and path == "/products/admin":
        return format_response(delete_product(query_params.get("product_id")))
    if path == "/products/search" and http_method == "POST":
        return format_response(search_products(query_params))

    if path == "/products/details" and http_method == "GET":
        return format_response(get_product_with_short_variants(query_params.get("product_id")))

    if path == "/products/variant" and http_method == "GET":
        return format_response(get_full_variant(query_params.get("product_id"), query_params.get("variant_id")))

    if path == "/products/admin/variant":
        if http_method == "POST":
            return format_response(add_variant(body))
        elif http_method == "PUT":
            return format_response(update_variant(body))
        elif http_method == "DELETE":
            return format_response(delete_variant(body))

    if path == "/products/category":
        if http_method == "GET":
            if "category" not in query_params:
                return format_response({"statusCode": 400, "body": {"error": "category query param required"}})
            return format_response(get_products_by_category(query_params["category"]))

    if path == "/products/admin/category/meta":
        if http_method == "POST":
            return format_response(store_category_metadata(body))
        elif http_method == "PUT":
            return format_response(update_category_metadata(body))
        elif http_method == "DELETE":
            if "category" not in query_params:
                return format_response({"statusCode": 400, "body": {"error": "category query param required"}})
            return format_response(delete_category_metadata(query_params["category"]))

    if path == "/products/categories/unique" and http_method == "GET":
        return format_response(find_unique_categories())

    if path == "/products/categories/all" and http_method == "GET":
        return format_response(get_all_categories_with_metadata())

    if path == "/products/requests":
        if http_method == "POST":
            return format_response(request_product(body))
        elif http_method == "GET":
            return format_response(search_requested_projects(query_params))
        elif http_method == "PUT":
            if "product_id" not in body:
                return format_response({"statusCode": 400, "body": {"error": "product_id body param required"}})
            return format_response(update_requested_project(body["product_id"], body))
        elif http_method == "DELETE":
            if "product_id" not in query_params:
                return format_response({"statusCode": 400, "body": {"error": "product_id query param required"}})
            return format_response(delete_requested_project(query_params["product_id"]))
            
    if path == "/products/requests/user" and http_method == "GET":
        if "user_id" not in query_params:
            return format_response({"statusCode": 400, "body": {"error": "user_id query param required"}})
        return format_response(get_requested_projects_by_user(query_params["user_id"]))

    if path == "/products/admin/requests/approve" and http_method == "PUT":
        if "product_id" not in body:
            return format_response({"statusCode": 400, "body": {"error": "product_id body param required"}})
        return format_response(approve_requested_project(body))
    
    return format_response({"statusCode": 404, "body": {"error": f"Route not found: {http_method} {path}"}})