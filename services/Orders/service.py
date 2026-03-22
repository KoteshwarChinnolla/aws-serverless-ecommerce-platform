import boto3
import uuid
from datetime import datetime
from botocore.exceptions import ClientError
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
import os
from razorpay_service import create_rzp_order, verify_rzp_signature, fetch_rzp, create_rzp_refund

ORDERS_TABLE = os.environ.get('ORDERS_TABLE', 'orders')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(ORDERS_TABLE)

VALID_TRANSITIONS = {
    "PENDING_PAYMENT": ["PLACED", "CANCELLED", "FAILED"],
    "PLACED": ["PROCESSING", "CANCELLED"],
    "PROCESSING": ["SHIPPED", "CANCELLED"],
    "SHIPPED": ["DELIVERED", "RETURNED"],
    "DELIVERED": ["RETURNED"],
    "CANCELLED": [],
    "FAILED": [],
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
            return obj
    if isinstance(obj, str):
        try:
            return Decimal(obj)
        except (InvalidOperation, ValueError):
            return obj
    if isinstance(obj, Decimal):
        return obj
    return obj



def init_checkout(body, user_id):

    required_fields = ["cart_id", "shipping_address", "line_items", "total_amount"]
    missing = [field for field in required_fields if not body.get(field)]
    
    if missing:
        return {'statusCode': 400, 'body': {"error": f"Missing required fields: {', '.join(missing)}"}}

    total_amount = float(body["total_amount"])
    internal_order_id = f"ORD-{str(uuid.uuid4())[:8].upper()}"
    current_time = datetime.utcnow().isoformat()

    rzp_res = create_rzp_order(total_amount, internal_order_id)
    if rzp_res['statusCode'] != 201:
        return {'statusCode': 500, 'body': {"error": "Payment gateway error", "details": rzp_res['body']}}
    
    razorpay_order_id = rzp_res['body']['id']

    # Create PENDING order in DB
    item = {
        "order_id": internal_order_id,
        "timestamp": current_time,
        "user_id": str(user_id),
        "cart_id": str(body["cart_id"]),
        "shipping_address": body["shipping_address"],
        "line_items": body["line_items"],
        "total_amount": Decimal(str(total_amount)),
        "razorpay_order_id": razorpay_order_id,
        "status": "PENDING_PAYMENT", # Lock state
        "payment_details": {}, # To be filled upon verification
        "updated_time": current_time
    }

    try:
        table.put_item(Item=native_to_decimal(item))
        return {
            'statusCode': 201, 
            'body': {
                "order_id": internal_order_id,
                "timestamp": current_time,
                "razorpay_order_id": razorpay_order_id,
                "amount": total_amount,
                "currency": "INR"
            }
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def verify_and_place_order(body, user_id):
    """STEP 2: Verifies Razorpay signature, updates DB to PLACED, saves payment payload."""
    order_id = body.get("order_id")
    timestamp = body.get("timestamp")
    rzp_order_id = body.get("razorpay_order_id")
    rzp_payment_id = body.get("razorpay_payment_id")
    rzp_signature = body.get("razorpay_signature")

    if not all([order_id, timestamp, rzp_order_id, rzp_payment_id, rzp_signature]):
        return {'statusCode': 400, 'body': {"error": "Missing verification parameters"}}

    # 1. Verify Signature Cryptographically
    is_valid = verify_rzp_signature(rzp_order_id, rzp_payment_id, rzp_signature)
    if not is_valid:
        # Mark order as FAILED
        table.update_item(
            Key={"order_id": str(order_id), "timestamp": str(timestamp)},
            UpdateExpression="SET #s = :status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":status": "FAILED"}
        )
        return {'statusCode': 400, 'body': {"error": "Invalid payment signature"}}

    # 2. Fetch actual payment details from Razorpay (method, card details, wallet used)
    payment_info = fetch_rzp({"payment_id": rzp_payment_id})
    payment_data = payment_info.get('body', {}) if payment_info['statusCode'] == 200 else {"id": rzp_payment_id}

    # 3. Securely Update Order to PLACED
    try:
        response = table.update_item(
            Key={"order_id": str(order_id), "timestamp": str(timestamp)},
            UpdateExpression="SET #s = :new_status, payment_details = :payment, updated_time = :time",
            ConditionExpression="attribute_exists(order_id) AND #s = :expected_status AND user_id = :uid",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":new_status": "PLACED",
                ":expected_status": "PENDING_PAYMENT",
                ":uid": str(user_id),
                ":payment": payment_data, # SAVES THE ACTUAL PAYMENT INFO TO THE DB
                ":time": datetime.utcnow().isoformat()
            },
            ReturnValues="ALL_NEW"
        )
        return {'statusCode': 200, 'body': {"message": "Order placed successfully", "order": decimal_to_native(response.get('Attributes'))}}
    except ClientError as e:
        return {'statusCode': 409, 'body': {"error": "Order already processed or not found."}}

def get_user_orders(user_id, limit=20, start_key=None):
    safe_limit = int(limit) if limit else 20
    query_kwargs = {
        "IndexName": "user_id_index",
        "KeyConditionExpression": Key("user_id").eq(str(user_id)),
        "ScanIndexForward": False,
        "Limit": safe_limit
    }
    if start_key: query_kwargs["ExclusiveStartKey"] = start_key

    try:
        response = table.query(**query_kwargs)
        return {"statusCode": 200, "body": {"orders": decimal_to_native(response.get("Items", [])), "next_page_token": response.get("LastEvaluatedKey")}}
    except ClientError as e:
        return {"statusCode": 500, "body": {"error": e.response["Error"]["Message"]}}

def admin_search_orders(filters):
    safe_limit = int(filters.get("limit")) if filters.get("limit") else 50
    start_key = filters.get("start_key")
    filter_expression = None
    
    for key in ["status", "user_id"]:
        if key in filters and filters[key]:
            expr = Attr(key).eq(str(filters[key]))
            filter_expression = expr if filter_expression is None else filter_expression & expr

    scan_kwargs = {"Limit": safe_limit}
    if filter_expression: scan_kwargs["FilterExpression"] = filter_expression
    if start_key: scan_kwargs["ExclusiveStartKey"] = start_key

    try:
        response = table.scan(**scan_kwargs)
        return {'statusCode': 200, 'body': {'orders': decimal_to_native(response.get("Items", [])), 'next_page_token': response.get("LastEvaluatedKey")}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def admin_update_status(body):
    order_id = body.get("order_id")
    timestamp = body.get("timestamp")
    new_status = body.get("status")
    current_status = body.get("current_status")
    
    if not all([order_id, timestamp, new_status, current_status]):
        return {'statusCode': 400, 'body': {"error": "order_id, timestamp, status, and current_status are required"}}

    new_status = new_status.upper()
    current_status = current_status.upper()

    if new_status not in VALID_TRANSITIONS.get(current_status, []):
        return {'statusCode': 400, 'body': {"error": f"Invalid transition from {current_status} to {new_status}"}}

    try:
        response = table.update_item(
            Key={"order_id": str(order_id), "timestamp": str(timestamp)},
            UpdateExpression="SET #s = :new_status, updated_time = :time",
            ConditionExpression="attribute_exists(order_id) AND #s = :current_status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":new_status": new_status,
                ":current_status": current_status,
                ":time": datetime.utcnow().isoformat()
            },
            ReturnValues="UPDATED_NEW"
        )
        return {'statusCode': 200, 'body': {"message": "Status updated", "order": decimal_to_native(response.get('Attributes'))}}
    except ClientError as e:
        return {'statusCode': 409, 'body': {"error": "Conflict: Order status changed or does not exist."}}

def get_order_by_id(order_id, timestamp):
    if not order_id or not timestamp: return {'statusCode': 400, 'body': {"error": "Missing keys"}}
    try:
        response = table.get_item(Key={"order_id": str(order_id), "timestamp": str(timestamp)})
        item = response.get('Item')
        return {'statusCode': 200, 'body': decimal_to_native(item)} if item else {'statusCode': 404, 'body': {"error": "Not found"}}
    except Exception as e:
        return {'statusCode': 500, 'body': {"error": str(e)}}

def cancel_order(body):
    """Cancels order and automatically triggers Razorpay refund if applicable."""
    order_id = body.get("order_id")
    timestamp = body.get("timestamp")
    current_status = body.get("current_status")
    
    if not all([order_id, timestamp, current_status]):
        return {'statusCode': 400, 'body': {"error": "order_id, timestamp, and current_status required"}}

    if current_status not in ["PLACED", "PROCESSING", "PENDING_PAYMENT"]:
        return {'statusCode': 400, 'body': {"error": f"Cannot cancel order in {current_status} status"}}
    
    order_res = get_order_by_id(order_id, timestamp)
    if order_res['statusCode'] != 200: return order_res
    order = order_res['body']

    # Handle Refunds for Paid Orders
    payments = order.get("payment_details", {})
    if payments and payments.get("id"):
        refund_response = create_rzp_refund(
            payment_id=payments["id"], 
            amount_in_rupees=order.get("total_amount", 0)
        )
        if refund_response.get("statusCode") != 201:
            return {'statusCode': 500, 'body': {"error": "Failed to create refund", "details": refund_response.get("body", {})}}

    # Update DB Status
    try:
        table.update_item(
            Key={"order_id": str(order_id), "timestamp": str(timestamp)},
            UpdateExpression="SET #s = :new_status, updated_time = :time",
            ConditionExpression="#s = :current_status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":new_status": "CANCELLED",
                ":current_status": current_status,
                ":time": datetime.utcnow().isoformat()
            }
        )
        return {'statusCode': 200, 'body': {"message": "Order successfully cancelled and refunded if applicable."}}
    except ClientError:
        return {'statusCode': 409, 'body': {"error": "Order status changed during cancellation."}}

