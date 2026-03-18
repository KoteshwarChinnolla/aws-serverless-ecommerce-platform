import boto3
import uuid
import time
from datetime import datetime
from botocore.exceptions import ClientError
from decimal import Decimal
import os
from boto3.dynamodb.conditions import Attr, Key


USERS_TABLE = os.environ.get('USERS_TABLE', 'users')

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(USERS_TABLE)

def decimal_to_native(obj):
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    if isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def create_user_profile(body):
    current_time = datetime.utcnow()
    human_timestamp = current_time.isoformat() 
    sort_timestamp = int(time.mktime(current_time.timetuple()) * 1000)

    # Allow custom user_id (e.g., from an Auth provider) or generate one
    user_id = body.get("user_id", str(uuid.uuid4()))

    item = {
        **body,
        "user_id": user_id,
        "created_at": human_timestamp,
        "created_at_ms": sort_timestamp
    }

    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(user_id)" # Prevents overwriting existing users
        )
        return {
            'statusCode': 201,
            'body': {"message": "User profile created successfully", "user_id": user_id}
        }

    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return {'statusCode': 409, 'body': {"error": "User ID already exists"}}
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def update_user_profile(body):
    """Updates an existing user's details."""
    user_id = body.get('user_id')
    if not user_id:
        return {'statusCode': 400, 'body': {"error": "user_id is required"}}

    update_expression = "SET "
    expression_attribute_values = {}
    expression_attribute_names = {}

    for key, value in body.items():
        if key not in ['user_id', 'created_at', 'created_at_ms']:
            expression_attribute_names[f"#{key}"] = key
            update_expression += f"#{key} = :{key}, "
            expression_attribute_values[f":{key}"] = value

    if update_expression == "SET ":
        return {'statusCode': 400, 'body': {"error": "No valid fields provided for update"}}

    # Add an updated_at timestamp automatically
    update_expression = update_expression.rstrip(", ")
    update_expression += ", #updated_at = :updated_at"
    expression_attribute_names["#updated_at"] = "updated_at"
    expression_attribute_values[":updated_at"] = datetime.utcnow().isoformat()

    try:
        response = table.update_item(
            Key={'user_id': user_id}, # Only user_id is needed per your SAM template
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW"
        )
        return {
            'statusCode': 200,
            'body': {'message': 'User profile updated', 'user': decimal_to_native(response.get('Attributes'))}
        }

    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def fetch_users_filters(body):
    
    filter_expr = None

    filters = ["name", "email", "phone", "city", "state"]
    
    for f in filters:
        if body.get(f):
            expr = Attr(f).begins_with(str(body[f]))
            filter_expr = expr if filter_expr is None else filter_expr & expr

    limit = int(body.get("limit", 100))
    scan_kwargs = {"Limit": limit}

    if filter_expr is not None:
        scan_kwargs["FilterExpression"] = filter_expr

    if body.get("cursor"):
        scan_kwargs["ExclusiveStartKey"] = body["cursor"]

    try:
        response = table.scan(**scan_kwargs)
        data = response.get('Items', [])
        
        return {
            'statusCode': 200,
            "body": {
                "users": decimal_to_native(data),
                "count": response.get("Count", 0),
                "next_cursor": response.get("LastEvaluatedKey")
            }
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def get_user_address(user_id):
    """Extracts only the address object for a specific user."""
    if not user_id:
        return {'statusCode': 400, 'body': {"error": "user_id is required"}}

    try:
        response = table.get_item(Key={"user_id": str(user_id)})
        item = response.get("Item")

        if not item:
            return {"statusCode": 404, "body": {"error": "User not found"}}

        return {
            "statusCode": 200,
            "body": {"address": decimal_to_native(item.get("address"))}
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def fetch_user_by_id(user_id):
    """Fetches a complete user profile by user_id."""
    try:
        response = table.get_item(Key={"user_id": str(user_id)})
        item = response.get("Item")

        if not item:
            return {"statusCode": 404, "body": {"error": "User not found"}}

        return {
            "statusCode": 200,
            "body": decimal_to_native(item)
        }
    except Exception as e:
        return {"statusCode": 500, "body": {"error": str(e)}}


def fetch_user_by_email(email):
    """NEW: Uses the Global Secondary Index defined in your SAM template to find a user by email."""
    if not email:
        return {'statusCode': 400, 'body': {"error": "email is required"}}
        
    try:
        response = table.query(
            IndexName="email_index",
            KeyConditionExpression=Key("email").eq(email)
        )
        items = response.get("Items", [])
        
        if not items:
            return {"statusCode": 404, "body": {"error": "User not found with this email"}}
            
        return {
            "statusCode": 200,
            "body": decimal_to_native(items[0])
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def fetch_all_users():
    """Retrieves all users (Not recommended for large datasets)."""
    try:
        response = table.scan()
        data = response.get('Items', [])
        return {
            'statusCode': 200,
            'body': {"users": decimal_to_native(data)}
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def delete_user(user_id):
    """Deletes a user profile."""
    if not user_id:
        return {'statusCode': 400, 'body': {"error": "user_id is required"}}

    try:
        response = table.delete_item(
            Key={'user_id': str(user_id)}
        )
        return {
            'statusCode': 200,
            'body': {"message": "User deleted successfully"}
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}