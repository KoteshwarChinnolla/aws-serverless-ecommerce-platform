import boto3
import uuid
import time
from datetime import datetime
from botocore.exceptions import ClientError
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
import os
from common import table, decimal_to_native, native_to_decimal

ENTITY_PRODUCT = "PRODUCT"

def create_product(body):
    """Creates a production-grade base product."""
    product_id = body.get("product_id") or f"PROD-{str(uuid.uuid4())[:8].upper()}"
    current_time = datetime.utcnow().isoformat()

    # Production Schema Definition
    item = {
        "product_id": product_id,
        "entity_type": ENTITY_PRODUCT,
        
        # Core Info
        "name": body.get("name", "").strip(),
        "slug": body.get("slug", "").lower().replace(" ", "-"), # For SEO URLs
        "description": body.get("description", ""),
        "short_description": body.get("short_description", ""),
        
        # Classification
        "category": body.get("category", "").lower(),
        "sub_category": body.get("sub_category", "").lower(),
        "brand": body.get("brand", ""),
        "tags": body.get("tags", []), # List of strings for search
        
        # Pricing & Display (Defaults if variants aren't used)
        "base_price": Decimal(str(body.get("base_price", 0))),
        "compare_at_price": Decimal(str(body.get("compare_at_price", 0))), # MRP
        "images": body.get("images", []), # Array of URLs
        "thumbnail": body.get("thumbnail", ""), 
        
        # State
        "status": body.get("status", "DRAFT").upper(), # DRAFT, ACTIVE, ARCHIVED
        "is_trending": body.get("is_trending", False),
        
        # Meta
        "seo_title": body.get("seo_title", ""),
        "seo_description": body.get("seo_description", ""),
        "created_at": current_time,
        "updated_at": current_time
    }

    try:
        table.put_item(Item=native_to_decimal(item))
        return {'statusCode': 201, 'body': {"message": "Product created", "product_id": product_id}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def update_product(body):
    
    product_id = body.get('product_id')
    if not product_id:
        return {'statusCode': 400, 'body': {"error": 'product_id is required'}}

    body['updated_at'] = datetime.utcnow().isoformat()
    # Protect system fields
    update_fields = {k: v for k, v in body.items() if k not in ['product_id', 'entity_type', 'created_at']}

    update_expression = "SET "
    expr_names = {}
    expr_values = {}

    for i, (key, value) in enumerate(update_fields.items()):
        name_key = f"#k{i}"
        value_key = f":v{i}"
        update_expression += f"{name_key} = {value_key}, "
        expr_names[name_key] = key
        expr_values[value_key] = value

    update_expression = update_expression.rstrip(", ")

    try:
        table.update_item(
            Key={'product_id': product_id, "entity_type": ENTITY_PRODUCT}, 
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=native_to_decimal(expr_values),
            ConditionExpression="attribute_exists(product_id)",
            ReturnValues="UPDATED_NEW"
        )
        return {'statusCode': 200, 'body': {"message": 'Product updated successfully'}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def search_products(filters):
    """Production search with pagination and active-only filters."""
    limit = int(filters.get("limit", 20))
    start_key = filters.get("start_key")
    
    # Always scope to Products
    filter_expression = Attr("entity_type").eq(ENTITY_PRODUCT)
    
    # Default to only showing ACTIVE products unless requested otherwise
    status = filters.get("status", "ACTIVE").upper()
    if status != "ALL":
        filter_expression &= Attr("status").eq(status)

    if filters.get("category"):
        filter_expression &= Attr("category").eq(str(filters["category"]).lower())
    if filters.get("is_trending") is not None:
        filter_expression &= Attr("is_trending").eq(filters["is_trending"])
    if filters.get("min_price"):
        filter_expression &= Attr("base_price").gte(Decimal(str(filters["min_price"])))
    if filters.get("max_price"):
        filter_expression &= Attr("base_price").lte(Decimal(str(filters["max_price"])))

    scan_kwargs = {
        "FilterExpression": filter_expression,
        "Limit": limit,
        "ProjectionExpression": "product_id, #n, slug, base_price, compare_at_price, images, category, is_trending",
        "ExpressionAttributeNames": {"#n": "name"}
    }
    
    if start_key:
        scan_kwargs["ExclusiveStartKey"] = start_key

    try:
        response = table.scan(**scan_kwargs)
        return {
            'statusCode': 200, 
            'body': {
                'count': len(response.get("Items", [])), 
                'products': decimal_to_native(response.get("Items", [])),
                'next_page_token': response.get("LastEvaluatedKey")
            }
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def delete_product(product_id):
    if not product_id:
        return {'statusCode': 400, 'body': {"error": 'product_id is required'}}
    try:
        table.update_item(
            Key={"product_id": str(product_id), "entity_type": ENTITY_PRODUCT},
            UpdateExpression="SET #s = :status, updated_at = :time",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "ARCHIVED",
                ":time": datetime.utcnow().isoformat()
            },
            ConditionExpression="attribute_exists(product_id)"
        )
        return {'statusCode': 200, 'body': {"message": 'Product archived successfully'}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}