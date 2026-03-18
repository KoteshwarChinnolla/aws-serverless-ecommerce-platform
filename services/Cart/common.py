from decimal import Decimal
import uuid


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