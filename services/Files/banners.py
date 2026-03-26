import json
import os
import uuid
import boto3
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import os

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("BANNERS_TABLE", "banners")
table = dynamodb.Table(TABLE_NAME)

BANNERS_PK_PREFIX = "BANNER#"
BANNERS_SK = "BANNERS"

def _response(body, status=200):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*" # Essential for frontend CORS
        },
        "body": json.dumps(body, default=str)
    }

def _now():
    return datetime.utcnow().isoformat()

def _shorten(banner):
    if not banner: return None
    excluded_keys = {"updated_at", "internal_notes"} 
    return {k: v for k, v in banner.items() if k not in excluded_keys}


def create_banner(body):
    if not body.get("name") or not body.get("media"):
        return _response({"error": "name and media are required"}, 400)

    banner_id = f"{BANNERS_PK_PREFIX}{str(uuid.uuid4())[:8].upper()}"
    timestamp = _now()
    
    item = {
        "name": body["name"],
        "media": body.get("media", []),
        "description": body.get("description", ""),
        "link": body.get("link", ""),
        "internal_notes": body.get("internal_notes", ""),
        "banner_id": banner_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "is_active": body.get("is_active", True)
    }

    try:
        table.put_item(Item={
            "PK": banner_id,
            "SK": BANNERS_SK,
            **item
        })
        return _response({"message": "Created", "banner": _shorten(item)}, 201)
    except ClientError as e:
        return _response({"error": str(e)}, 500)

def update_banner(banner_id, body):
    if not banner_id:
        return _response({"error": "banner_id is required"}, 400)

    update_expression = "SET "
    expression_values = {}
    allowed_fields = {"name", "media", "description", "link", "internal_notes", "is_active"}

    for key in allowed_fields:
        if key in body:
            update_expression += f"{key} = :{key}, "
            expression_values[f":{key}"] = body[key]

    if not expression_values:
        return _response({"error": "No valid fields to update"}, 400)

    update_expression += "updated_at = :updated_at"
    expression_values[":updated_at"] = _now()

    try:
        table.update_item(
            # FIXED KEY SCHEMA HERE
            Key={"PK": banner_id, "SK": BANNERS_SK},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ConditionExpression="attribute_exists(PK)" # Changed from banner_id to PK
        )
        return _response({"message": "Updated"})
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _response({"error": "Banner not found"}, 404)
        return _response({"error": str(e)}, 500)

def get_banner(banner_id):
    if not banner_id:
        return _response({"error": "banner_id is required"}, 400)

    try:
        # FIXED KEY SCHEMA HERE
        response = table.get_item(Key={"PK": banner_id, "SK": BANNERS_SK})
        if "Item" not in response:
            return _response({"error": "Banner not found"}, 404)
        return _response(response["Item"])
    except ClientError as e:
        return _response({"error": str(e)}, 500)


def delete_banner(banner_id):
    if not banner_id:
        return _response({"error": "banner_id is required"}, 400)

    try:
        # FIXED KEY SCHEMA HERE
        table.delete_item(
            Key={"PK": banner_id, "SK": BANNERS_SK},
            ConditionExpression="attribute_exists(PK)" # Changed from banner_id to PK
        )
        return _response({"message": "Banner deleted"})
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _response({"error": "Banner not found"}, 404)
        return _response({"error": str(e)}, 500)
  
def get_all_banners(query_params):
    try:
        response = table.scan()
        items = response.get("Items", [])

        if query_params.get("is_active") is not None:
            is_active = query_params["is_active"].lower() == "true"
            items = [b for b in items if b.get("is_active") == is_active]
            
        short_banners = [_shorten(item) for item in items]
        return _response({"count": len(items), "banners": short_banners})
    except ClientError as e:
        return _response({"error": str(e)}, 500)
    