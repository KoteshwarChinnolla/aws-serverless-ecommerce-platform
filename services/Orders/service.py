import boto3
import uuid
from datetime import datetime
from botocore.exceptions import ClientError
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
import os

# Fetch table name dynamically from environment variables
ORDERS_TABLE = os.environ.get('ORDERS_TABLE', 'orders')

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(ORDERS_TABLE)

def decimal_to_native(obj):
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    if isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def short_order(order):
    return {
        "order_id": order.get("order_id"),
        "user_id": order.get("user_id"),
        "timestamp": order.get("timestamp"),
        "status": order.get("status", "PLACED"),
        "product_name": order.get("product_name", "Standard Product"),
        "total_amount": order.get("total_amount", "COD")
    }

def create_order(body):
    user_id = body.get("user_id")
    if not user_id:
        return {'statusCode': 400, 'body': {"error": "user_id is required"}}

    current_time = datetime.utcnow().isoformat()
    order_id = str(uuid.uuid4())

    item = {
        **body,
        "order_id": order_id,
        "user_id": user_id,
        "timestamp": current_time,
        "updated_time": current_time,
        "status": body.get("status", "PLACED")
    }

    try:
        table.put_item(Item=item)
        return {
            'statusCode': 201, 
            'body': {
                "message": "Order created successfully", 
                "order_id": order_id, 
                "timestamp": current_time
            }
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def update_order(body):
    """Updates an existing order."""
    order_id = body.get("order_id")
    timestamp = body.get("timestamp")
    
    if not order_id or not timestamp:
        return {'statusCode': 400, 'body': {"error": "order_id and timestamp are required for updates"}}

    body["updated_time"] = datetime.utcnow().isoformat()

    # Filter out keys we shouldn't update
    update_fields = {k: v for k, v in body.items() if k not in ["order_id", "timestamp", "user_id"]}

    if not update_fields:
        return {'statusCode': 400, 'body': {"error": "No valid fields provided to update"}}

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
        response = table.update_item(
            Key={
                "order_id": str(order_id),
                "timestamp": str(timestamp)
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW"
        )
        return {'statusCode': 200, 'body': {"message": "Order updated successfully", "order": decimal_to_native(response.get('Attributes'))}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def delete_order(order_id, timestamp):
    """Deletes an order."""
    if not order_id or not timestamp:
        return {'statusCode': 400, 'body': {"error": "order_id and timestamp are required"}}

    try:
        table.delete_item(
            Key={
                "order_id": str(order_id),
                "timestamp": str(timestamp)
            }
        )
        return {'statusCode': 200, 'body': {"message": "Order deleted successfully"}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def get_order_by_id(order_id, timestamp):
    """Fetches a specific order."""
    if not order_id or not timestamp:
        return {'statusCode': 400, 'body': {"error": "order_id and timestamp are required"}}
        
    try:
        response = table.get_item(Key={"order_id": str(order_id), "timestamp": str(timestamp)})
        item = response.get('Item')
        
        if item:
            return {'statusCode': 200, 'body': decimal_to_native(item)}
        else:
            return {'statusCode': 404, 'body': {"error": "Order not found"}}
    except Exception as e:
        return {'statusCode': 500, 'body': {"error": str(e)}}

def get_orders_by_user(user_id, short=False):
    """Fetches all orders for a specific user utilizing the GSI."""
    if not user_id:
        return {"statusCode": 400, "body": {"error": "user_id is required"}}

    try:
        response = table.query(
            IndexName="user_id_index",
            KeyConditionExpression=Key("user_id").eq(str(user_id)),
            ScanIndexForward=False # Latest orders first (assuming ISO timestamp sorts nicely)
        )
        items = response.get("Items", [])
        
        if short:
            items = [short_order(item) for item in items]

        return {"statusCode": 200, "body": {"count": len(items), "orders": decimal_to_native(items)}}
    except ClientError as e:
        return {"statusCode": 500, "body": {"error": e.response["Error"]["Message"]}}

def filter_orders(filters):
    """Scans and filters all orders based on custom form fields."""
    filter_expression = None
    
    # Example fields to filter by
    for key in ["status", "product_name", "user_id"]:
        if key in filters and filters[key]:
            expr = Attr(key).eq(str(filters[key]))
            filter_expression = expr if filter_expression is None else filter_expression & expr

    scan_kwargs = {}
    if filter_expression:
        scan_kwargs["FilterExpression"] = filter_expression

    try:
        items = []
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

        # Handle pagination
        while "LastEvaluatedKey" in response:
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            response = table.scan(**scan_kwargs)
            items.extend(response.get("Items", []))

        return {'statusCode': 200, 'body': {'count': len(items), 'orders': decimal_to_native(items)}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def get_all_orders_short():
    """Fetches a summary view of all orders in the system."""
    try:
        response = table.scan()
        data = response.get('Items', [])
        short_data = [short_order(item) for item in data]
        return {'statusCode': 200, 'body': {"count": len(short_data), "orders": decimal_to_native(short_data)}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

        