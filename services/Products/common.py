import boto3
import os
from decimal import Decimal

PRODUCTS_TABLE = os.environ.get('PRODUCTS_TABLE', 'products')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(PRODUCTS_TABLE)

def decimal_to_native(obj):
    """Recursively converts DynamoDB Decimal types to native Python types."""
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    if isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def native_to_decimal(obj):
    """Recursively converts native Python types to DynamoDB Decimal types."""
    if isinstance(obj, list):
        return [native_to_decimal(i) for i in obj]
    if isinstance(obj, dict):
        return {k: native_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, (int, float)):
        return Decimal(str(obj))
    return obj

def short_product(prod):
    """Formats a product for list/thumbnail views."""
    return {
        'image': prod.get('image_key', ""),
        'product_id': prod.get('product_id'),
        'entity_type': prod.get('entity_type'),
        'name': prod.get('name'),
        'category': prod.get('category'),
        'description': prod.get('description', "")[:100] + ("..." if len(prod.get('description', "")) > 100 else ""),
        'location': prod.get('location'),
        'price': f"₹{prod.get('selling_price')} (MRP: ₹{prod.get('mrp')})",
        'delivery_time': f"{prod.get('min_delivery_days')} - {prod.get('max_delivery_days')} days",
    }