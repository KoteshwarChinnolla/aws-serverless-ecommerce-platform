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
from decimal import Decimal, InvalidOperation

def native_to_decimal(obj):

    if obj is None:
        return None

    if isinstance(obj, list):
        return [native_to_decimal(i) for i in obj]

    if isinstance(obj, dict):
        return {k: native_to_decimal(v) for k, v in obj.items()}

    if isinstance(obj, bool):
        return obj

    if isinstance(obj, (int, float)):
        try:
            return Decimal(str(obj))
        except (InvalidOperation, ValueError):
            return obj  # or raise custom error

    if isinstance(obj, str):
        try:
            return Decimal(obj)
        except (InvalidOperation, ValueError):
            return obj  # keep as string

    if isinstance(obj, Decimal):
        return obj

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