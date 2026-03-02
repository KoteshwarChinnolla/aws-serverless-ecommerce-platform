import boto3
import json
import uuid
import time
from datetime import datetime
from botocore.exceptions import ClientError
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
import os
from common import table, decimal_to_native, short_product

ENTITY_PRODUCT = "PRODUCT"
ENTITY_META = "CATEGORY_META"

def store_product_data(body):
    current_time = datetime.utcnow()
    product_id = body.get("product_id") or str(uuid.uuid4())

    item = {
        **body,
        "product_id": product_id,
        "entity_type": ENTITY_PRODUCT,  # SORT KEY
        "name": body.get("name", "").lower(),
        "category": body.get("category", "").lower(),
        "location": body.get("location", "").lower(),
        "created_at": current_time.isoformat(),
        "time": int(time.mktime(current_time.timetuple()) * 1000),
    }

    try:
        table.put_item(Item=item)
        return {'statusCode': 201, 'body': {"message": "Product stored successfully", "product_id": product_id}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}
    
def store_category_metadata(body):
    category_name = body.get("category", "").lower()
    if not category_name:
        return {'statusCode': 400, 'body': {"error": "Category name is required"}}

    meta_id = f"META#{category_name}"
    
    item = {
        **body,
        "product_id": meta_id,
        "entity_type": ENTITY_META,  # SORT KEY
        "category": category_name,
        "updated_at": datetime.utcnow().isoformat()
    }

    try:
        table.put_item(Item=item)
        return {'statusCode': 200, 'body': {"message": f"Metadata for {category_name} updated."}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}
    

def get_product_by_id(product_id):
    if not product_id:
        return {'statusCode': 400, 'body': {"error": 'Missing product_id parameter'}}
        
    try:
        response = table.get_item(Key={"product_id": str(product_id), "entity_type": ENTITY_PRODUCT})
        item = response.get('Item')
        
        if item:
            return {'statusCode': 200, 'body': decimal_to_native(item)}
        else:
            return {'statusCode': 404, 'body': {"error": 'Product not found'}}
    except Exception as e:
        return {'statusCode': 500, 'body': {"error": str(e)}}

def fetch_all_products():
    try:
        # Filter out metadata rows automatically
        response = table.scan(
            FilterExpression=Attr("entity_type").eq(ENTITY_PRODUCT)
        )
        data = response.get('Items', [])
        formatted_data = [short_product(item) for item in data]
        return {'statusCode': 200, 'body': {"products": decimal_to_native(formatted_data)}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def get_products_filters(filters=None):
    """
    Supported filters: product_id, category, name, location, mrp, selling_price, delivery bounds
    """
    filter_expression = Attr("entity_type").eq(ENTITY_PRODUCT)
    
    if filters:
        if "product_id" in filters and filters["product_id"]:
            filter_expression &= Attr("product_id").eq(str(filters["product_id"]))

        if "category" in filters and filters["category"]:
            filter_expression &= Attr("category").eq(str(filters["category"].lower()))

        if "name" in filters and filters["name"]:
            filter_expression &= Attr("name").begins_with(str(filters["name"].lower()))

        if "location" in filters and filters["location"]:
            filter_expression &= Attr("location").begins_with(str(filters["location"].lower()))

        if "min_delivery_days" in filters and filters["min_delivery_days"]:
            filter_expression &= Attr("min_delivery_days").gte(Decimal(filters["min_delivery_days"]))

        if "max_delivery_days" in filters and filters["max_delivery_days"]:
            filter_expression &= Attr("max_delivery_days").lte(Decimal(filters["max_delivery_days"]))
        
        if "min_price" in filters and filters["min_price"]:
            filter_expression &= Attr("selling_price").gte(Decimal(filters["min_price"]))

        if "max_price" in filters and filters["max_price"]:
            filter_expression &= Attr("selling_price").lte(Decimal(filters["max_price"]))

    scan_kwargs = {"FilterExpression": filter_expression}

    try:
        items = []
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        
        formatted_items = [short_product(item) for item in items]

        while "LastEvaluatedKey" in response:
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            response = table.scan(**scan_kwargs)
            items.extend(response.get("Items", []))
            formatted_items.extend([short_product(item) for item in response.get("Items", [])])

        return {'statusCode': 200, 'body': {'count': len(formatted_items), 'products': decimal_to_native(formatted_items)}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def delete_product(product_id):
    try:
        table.delete_item(
            Key={"product_id": str(product_id), "entity_type": ENTITY_PRODUCT},
            ConditionExpression="attribute_exists(product_id)"
        )
        return {'statusCode': 200, 'body': {"message": 'Product deleted successfully'}}
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
             return {'statusCode': 404, 'body': {"error": 'Product not found'}}
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def update_product(body):
    product_id = body.get('product_id')
    if not product_id:
        return {'statusCode': 400, 'body': {"error": 'product_id is required'}}

    body['updated_at'] = datetime.utcnow().isoformat()
    update_fields = {k: v for k, v in body.items() if k not in ['product_id', 'time', 'created_at']}

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
            ExpressionAttributeValues=expr_values,
            ReturnValues="UPDATED_NEW"
        )
        return {'statusCode': 200, 'body': {"message": 'Product updated successfully'}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}
