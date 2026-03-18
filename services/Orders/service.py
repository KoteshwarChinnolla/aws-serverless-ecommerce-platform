import boto3
import uuid
from datetime import datetime
from botocore.exceptions import ClientError
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
import os

ORDERS_TABLE = os.environ.get('ORDERS_TABLE', 'orders')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(ORDERS_TABLE)

# Allowed order state transitions
VALID_TRANSITIONS = {
    "PLACED": ["PROCESSING", "CANCELLED"],
    "PROCESSING": ["SHIPPED", "CANCELLED"],
    "SHIPPED": ["DELIVERED", "RETURNED"],
    "DELIVERED": ["RETURNED"],
    "CANCELLED": [],
    "RETURNED": []
}

def decimal_to_native(obj):
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    if isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def create_order(body):

    # 1. Strict Validation: Enforce required fields
    required_fields = ["user_id", "cart_id", "shipping_address", "line_items", "total_amount"]
    missing = [field for field in required_fields if not body.get(field)]
    
    if missing:
        return {'statusCode': 400, 'body': {"error": f"Missing required fields: {', '.join(missing)}"}}

    if not isinstance(body["line_items"], list) or len(body["line_items"]) == 0:
        return {'statusCode': 400, 'body': {"error": "line_items must be a non-empty array"}}

    current_time = datetime.utcnow().isoformat()
    order_id = f"ORD-{str(uuid.uuid4())[:8].upper()}" # Friendly Order ID

    # 2. Schema Enforcement: Do not use **body. Explicitly map allowed fields.
    item = {
        "order_id": order_id,
        "timestamp": current_time,
        "user_id": str(body["user_id"]),
        "cart_id": str(body["cart_id"]),
        "shipping_address": body["shipping_address"], # Should be a dictionary
        "line_items": body["line_items"],             # Array of item dictionaries
        "total_amount": Decimal(str(body["total_amount"])),
        "payment_reference": body.get("payment_reference", "UNKNOWN"), # From payment gateway
        "status": "PLACED",
        "updated_time": current_time
    }

    try:
        # 3. Idempotency Check (Optional but recommended): Ensure order isn't created twice for same cart
        # (Requires a GSI on cart_id to check if it already exists, skipped here for brevity)
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

def update_order_status(body):
    """
    Replaces generic 'update_order'. In production, you only update specific things 
    like Status or Tracking Info. You never let a user update 'total_amount'.
    """
    order_id = body.get("order_id")
    timestamp = body.get("timestamp")
    new_status = body.get("status")
    current_status = body.get("current_status") # Required for atomic state machine
    
    if not all([order_id, timestamp, new_status, current_status]):
        return {'statusCode': 400, 'body': {"error": "order_id, timestamp, status, and current_status are required"}}

    new_status = new_status.upper()
    current_status = current_status.upper()

    # 1. State Machine Validation
    allowed_next_states = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed_next_states:
        return {'statusCode': 400, 'body': {"error": f"Invalid transition from {current_status} to {new_status}"}}

    try:
        # 2. Atomic Update: Fails if the database status doesn't match 'current_status'
        response = table.update_item(
            Key={
                "order_id": str(order_id),
                "timestamp": str(timestamp)
            },
            UpdateExpression="SET #s = :new_status, updated_time = :time",
            ConditionExpression="attribute_exists(order_id) AND #s = :current_status",
            ExpressionAttributeNames={
                "#s": "status"
            },
            ExpressionAttributeValues={
                ":new_status": new_status,
                ":current_status": current_status,
                ":time": datetime.utcnow().isoformat()
            },
            ReturnValues="UPDATED_NEW"
        )
        return {'statusCode': 200, 'body': {"message": "Status updated", "updated_data": decimal_to_native(response.get('Attributes'))}}
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
             return {'statusCode': 409, 'body': {"error": "Conflict: Order status changed by another process or does not exist."}}
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def get_order_by_id(order_id, timestamp):
    if not order_id or not timestamp:
        return {'statusCode': 400, 'body': {"error": "order_id and timestamp are required"}}
        
    try:
        response = table.get_item(Key={"order_id": str(order_id), "timestamp": str(timestamp)})
        item = response.get('Item')
        if item:
            return {'statusCode': 200, 'body': decimal_to_native(item)}
        return {'statusCode': 404, 'body': {"error": "Order not found"}}
    except Exception as e:
        return {'statusCode': 500, 'body': {"error": str(e)}}

def get_orders_by_user(user_id, limit=20, start_key=None):
    """Production version utilizing pagination."""
    if not user_id:
        return {"statusCode": 400, "body": {"error": "user_id is required"}}

    query_kwargs = {
        "IndexName": "user_id_index",
        "KeyConditionExpression": Key("user_id").eq(str(user_id)),
        "ScanIndexForward": False,
        "Limit": int(limit)
    }
    
    if start_key:
        query_kwargs["ExclusiveStartKey"] = start_key

    try:
        response = table.query(**query_kwargs)
        items = response.get("Items", [])
        
        return {
            "statusCode": 200, 
            "body": {
                "orders": decimal_to_native(items),
                "next_page_token": response.get("LastEvaluatedKey") # Pass back to frontend
            }
        }
    except ClientError as e:
        return {"statusCode": 500, "body": {"error": e.response["Error"]["Message"]}}

def filter_orders(filters):
    """Production search with Limits and Pagination to prevent Lambda timeouts."""
    limit = int(filters.get("limit", 50))
    start_key = filters.get("start_key")
    
    filter_expression = None
    
    for key in ["status", "user_id"]:
        if key in filters and filters[key]:
            expr = Attr(key).eq(str(filters[key]))
            filter_expression = expr if filter_expression is None else filter_expression & expr

    scan_kwargs = {"Limit": limit}
    if filter_expression:
        scan_kwargs["FilterExpression"] = filter_expression
    if start_key:
        scan_kwargs["ExclusiveStartKey"] = start_key

    try:
        # NO WHILE LOOP! Return a single page of results.
        response = table.scan(**scan_kwargs)
        
        return {
            'statusCode': 200, 
            'body': {
                'orders': decimal_to_native(response.get("Items", [])),
                'next_page_token': response.get("LastEvaluatedKey")
            }
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


