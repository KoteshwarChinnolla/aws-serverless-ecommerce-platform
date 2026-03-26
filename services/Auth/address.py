import json
import os
import uuid
import boto3
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import os

dynamodb = boto3.resource("dynamodb")
USERS_TABLE = os.environ.get("USERS_TABLE", "users")
table = dynamodb.Table(USERS_TABLE)

ADDRESS_PK_PREFIX = "ADDRESS#"
ADDRESS_SK = "ADDRESS"


def add_address(body):
    user_id = body.get("user_id")
    if not user_id:
        return {"statusCode": 400, "body": {"error": "user_id is required"}}

    address_id = f"{ADDRESS_PK_PREFIX}{str(uuid.uuid4())[:8].upper()}"
    timestamp = datetime.utcnow().isoformat()

    item = {
        "user_id": str(user_id),
        "name": body.get("name", ""),
        "phone": body.get("phone", ""),
        "email": body.get("email", ""),
        "default": body.get("default", False),
        "address_id": address_id,
        "entity_type": ADDRESS_SK,
        "line1": body.get("line1", ""),
        "line2": body.get("line2", ""),
        "city": body.get("city", ""),
        "state": body.get("state", ""),
        "postal_code": body.get("postal_code", ""),
        "country": body.get("country", ""),
        "created_at": timestamp,
        "updated_at": timestamp
    }

    try:
        table.put_item(Item={
            "PK": f"{ADDRESS_PK_PREFIX}{user_id}",
            "SK": address_id,
            **item
        })
        return {"statusCode": 200, "body": item}
    except ClientError as e:
        return {"statusCode": 500, "body": {"error": str(e)}}
    
def get_addresses(user_id):
    if not user_id:
        return {"statusCode": 400, "body": {"error": "user_id is required"}}

    try:
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"{ADDRESS_PK_PREFIX}{user_id}") & Key("SK").begins_with(ADDRESS_PK_PREFIX)
        )
        items = response.get("Items", [])
        return {"statusCode": 200, "body": items}
    except ClientError as e:
        return {"statusCode": 500, "body": {"error": str(e)}}
    
def delete_address(user_id, address_id):
    if not user_id or not address_id:
        return {"statusCode": 400, "body": {"error": "user_id and address_id are required"}}

    try:
        table.delete_item(
            Key={
                "PK": f"{ADDRESS_PK_PREFIX}{user_id}",
                "SK": address_id
            }
        )
        return {"statusCode": 200, "body": {"message": "Address deleted"}}
    except ClientError as e:
        return {"statusCode": 500, "body": {"error": str(e)}}



def update_address(body):
    user_id = body.get("user_id")
    address_id = body.get("address_id")
    if not user_id or not address_id:
        return {"statusCode": 400, "body": {"error": "user_id and address_id are required"}}

    update_expression = "SET "
    expression_values = {}
    expression_names = {}
    allowed_fields = {"name", "phone", "email", "default", "line1", "line2", "city", "state", "postal_code", "country"}

    for key in allowed_fields:
        if key in body:
            placeholder = f":{key}"
            if key == "state":  # reserved keyword
                update_expression += f"#state = {placeholder}, "
                expression_names["#state"] = "state"
            else:
                update_expression += f"{key} = {placeholder}, "
            expression_values[placeholder] = body[key]

    if not expression_values:
        return {"statusCode": 400, "body": {"error": "No valid fields to update"}}

    update_expression += "updated_at = :updated_at"
    expression_values[":updated_at"] = datetime.utcnow().isoformat()

    try:
        table.update_item(
            Key={
                "PK": f"{ADDRESS_PK_PREFIX}{user_id}",
                "SK": address_id
            },
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names if expression_names else None
        )
        return {"statusCode": 200, "body": {"message": "Address updated"}}
    except ClientError as e:
        return {"statusCode": 500, "body": {"error": str(e)}}