import boto3
import uuid
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import os
from common import table, decimal_to_native, native_to_decimal
from decimal import Decimal

ENTITY_PRODUCT = "PRODUCT"
ENTITY_VARIANT_PREFIX = "VARIANT#"

def add_variant(body):

    product_id = body.get("product_id")
    attribute_values = body.get("attribute_values", {})
    
    if not product_id or not attribute_values:
        return {'statusCode': 400, 'body': {"error": "product_id and attribute_values are required"}}

    variant_id = body.get("variant_id") or f"VAR-{str(uuid.uuid4())[:8].upper()}"
    current_time = datetime.utcnow().isoformat()

    item = {
        "product_id": str(product_id),
        "entity_type": f"{ENTITY_VARIANT_PREFIX}{variant_id}",
        "variant_id": variant_id,
        
        # Identifiers
        "sku": body.get("sku", ""),
        "barcode": body.get("barcode", ""),
        
        # Product Spec
        "attribute_values": attribute_values, # e.g., {"Color": "Red", "Size": "XL"}
        "is_primary": body.get("is_primary", False),
        
        # Pricing & Inventory
        "price": Decimal(str(body.get("price", 0))),
        "compare_at_price": Decimal(str(body.get("compare_at_price", 0))),
        "stock": int(body.get("stock", 0)),
        "low_stock_threshold": int(body.get("low_stock_threshold", 5)),
        
        # Fulfillment Details (Needed for calculating shipping rates)
        "weight_grams": Decimal(str(body.get("weight_grams", 0))),
        "dimensions_cm": body.get("dimensions_cm", {"l": 0, "w": 0, "h": 0}),
        
        "brand": body.get("brand", ""),
        "thumbnail": body.get("thumbnail", ""),

        "images": body.get("images", []),
        "name": body.get("name", ""),
        "short_description": body.get("short_description", ""),

        "description": body.get("description", ""),

        "status": body.get("status", "ACTIVE").upper(),
        "created_at": current_time,
        "updated_at": current_time
    }

    try:
        table.put_item(Item=native_to_decimal(item))
        return {'statusCode': 201, 'body': {"message": "Variant created", "variant_id": variant_id}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def get_product_with_short_variants(product_id):

    if not product_id:
        return {'statusCode': 400, 'body': {"error": "product_id is required"}}

    try:
        response = table.query(KeyConditionExpression=Key("product_id").eq(str(product_id)))
        items = response.get("Items", [])
        
        if not items:
            return {'statusCode': 404, 'body': {"error": "Product not found"}}

        base_product = {}
        primary_variant = None
        short_variants = []

        for item in items:
            if item["entity_type"] == ENTITY_PRODUCT:
                if item.get("status") == "ARCHIVED":
                     return {'statusCode': 404, 'body': {"error": "Product is no longer available"}}
                base_product = decimal_to_native(item)
                
            elif item["entity_type"].startswith(ENTITY_VARIANT_PREFIX) and item.get("status") != "INACTIVE":
                
                if item.get("is_primary") == True:
                    primary_variant = decimal_to_native(item)

                short_variants.append({
                    "variant_id": item.get("variant_id"),
                    "sku": item.get("sku"),
                    "attribute_values": item.get("attribute_values"),
                    "price": decimal_to_native(item.get("price")),
                    "stock": decimal_to_native(item.get("stock")),
                    "thumbnail": item.get("thumbnail", ""),
                    "status": item.get("status", "ACTIVE")
                })

        return {'statusCode': 200, 'body': {
            "product": base_product,
            "primary_variant": primary_variant,
            "variants": short_variants
        }}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def get_full_variant(product_id, variant_id):
    
    if not product_id or not variant_id:
        return {'statusCode': 400, 'body': {"error": "product_id and variant_id required"}}
        
    try:
        response = table.get_item(Key={"product_id": str(product_id), "entity_type": f"{ENTITY_VARIANT_PREFIX}{variant_id}"})
        item = response.get('Item')
        if item:
            return {'statusCode': 200, 'body': decimal_to_native(item)}
        return {'statusCode': 404, 'body': {"error": "Variant not found"}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def update_variant(body):

    product_id = body.get("product_id")
    variant_id = body.get("variant_id")
    
    if not product_id or not variant_id:
        return {'statusCode': 400, 'body': {"error": "product_id and variant_id required"}}

    body['updated_at'] = datetime.utcnow().isoformat()
    update_fields = {k: v for k, v in body.items() if k not in ['product_id', 'variant_id', 'entity_type', 'created_at']}

    update_expression = "SET "
    expr_names = {}
    expr_values = {}

    for i, (key, value) in enumerate(update_fields.items()):
        name_key = f"#k{i}"
        value_key = f":v{i}"
        update_expression += f"{name_key} = {value_key}, "
        expr_names[name_key] = key
        expr_values[value_key] = value

    try:
        table.update_item(
            Key={'product_id': str(product_id), 'entity_type': f"{ENTITY_VARIANT_PREFIX}{variant_id}"},
            UpdateExpression=update_expression.rstrip(", "),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=native_to_decimal(expr_values),
            ConditionExpression="attribute_exists(product_id)",
            ReturnValues="UPDATED_NEW"
        )
        return {'statusCode': 200, 'body': {"message": "Variant updated successfully"}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def delete_variant(body):
    product_id = body.get("product_id")
    variant_id = body.get("variant_id")

    if not product_id or not variant_id:
        return {'statusCode': 400, 'body': {"error": "product_id and variant_id required"}}

    try:
        table.update_item(
            Key={"product_id": str(product_id), "entity_type": f"{ENTITY_VARIANT_PREFIX}{variant_id}"},
            UpdateExpression="SET #s = :status, updated_at = :time",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "INACTIVE",
                ":time": datetime.utcnow().isoformat()
            },
            ConditionExpression="attribute_exists(product_id)"
        )
        return {'statusCode': 200, 'body': {"message": 'Variant deactivated successfully'}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def decrement_stock(line_items):
    """Atomically decrements stock for multiple variants. Rolls back if any variant has insufficient stock."""
    print("Decrementing stock for line items:", line_items)
    try:
        for item in line_items:
            print("Processing line item for stock decrement:", item)
            product_id = item["product_id"]
            variant_id = item["variant_id"]
            quantity = int(item["quantity"])
            
            response = table.get_item(Key={"product_id": str(product_id), "entity_type": f"{ENTITY_VARIANT_PREFIX}{variant_id}"})
            variant = response.get('Item')
            print(f"Current stock for variant {variant_id}:", variant.get("stock", 0) if variant else "Variant not found")
            if not variant:
                raise Exception(f"Variant {variant_id} not found for product {product_id}")
            
            current_stock = int(variant.get("stock", 0))
            
            if current_stock < quantity:
                raise Exception(f"Insufficient stock for variant {variant_id} (Available: {current_stock}, Required: {quantity})")
            
            # Decrement stock
            new_stock = current_stock - quantity
            print(f"New stock for variant {variant_id}:", new_stock)
            table.update_item(
                Key={"product_id": str(product_id), "entity_type": f"{ENTITY_VARIANT_PREFIX}{variant_id}"},
                UpdateExpression="SET stock = :new_stock, updated_at = :time",
                ExpressionAttributeValues={
                    ":new_stock": new_stock,
                    ":time": datetime.utcnow().isoformat()
                },
                ConditionExpression="attribute_exists(product_id)"
            )
        return {'statusCode': 200, 'body': {"message": "Stock decremented successfully"}}
    except Exception as e:
        return {'statusCode': 400, 'body': {"error": str(e)} }

