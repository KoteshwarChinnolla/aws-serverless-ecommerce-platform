import boto3
import uuid
import json
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import os
from common import table, decimal_to_native, native_to_decimal
from decimal import Decimal

ENTITY_PRODUCT = "PRODUCT"
ENTITY_REVIEW_PREFIX = "REVIEW#"
ENTITY_REVIEW_META = "REVIEW_META"


def _update_review_summary(product_id, rating, is_addition=True):
    """Atomically increments or decrements the review summary counters."""
    increment_val = 1 if is_addition else -1
    star_key = f"star_{rating}" # e.g., "star_5"

    try:
        table.update_item(
            Key={'product_id': str(product_id), 'entity_type': ENTITY_REVIEW_META},
            UpdateExpression="ADD total_reviews :inc, #star :inc",
            ExpressionAttributeNames={"#star": star_key},
            ExpressionAttributeValues={":inc": increment_val}
        )
    except ClientError as e:
        print(f"Failed to update review summary: {e}")


def create_review(body):
    product_id = body.get("product_id")
    user_id = body.get("user_id")
    
    if not product_id or not user_id:
        return {'statusCode': 400, 'body': {"error": "product_id and user_id are required"}}

    # Validate Rating Bounds (1 to 5)
    rating = int(body.get("rating", 1))
    rating = max(1, min(5, rating)) # Clamp between 1 and 5

    review_id = body.get("review_id") or f"REV-{str(uuid.uuid4())[:8].upper()}"
    current_time = datetime.utcnow().isoformat()

    item = {
        "product_id": str(product_id),
        "entity_type": f"{ENTITY_REVIEW_PREFIX}{review_id}",
        "review_id": review_id,
        "user_id": str(user_id),
        "reviewer_name": body.get("reviewer_name", "Anonymous"),
        "rating": rating,
        "comment": body.get("comment", "").strip(),
        "media": body.get("media", []),
        "likes": 0,
        "dislikes": 0,
        "status": "APPROVED", # Admins can set to HIDDEN
        "created_at": current_time,
        "updated_at": current_time
    }

    try:
        table.put_item(Item=native_to_decimal(item))
        
        _update_review_summary(product_id, rating, is_addition=True)
        return {'statusCode': 201, 'body': {"message": "Review created successfully", "review_id": review_id}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def get_product_reviews(query_params, is_admin=False):
    
    product_id = query_params.get("product_id")
    if not product_id:
        return {'statusCode': 400, 'body': {"error": "product_id is required"}}

    limit = int(query_params.get("limit", 10))
    sort_order = query_params.get("sort", "desc").lower()
    

    start_key = query_params.get("start_key")
    if start_key and isinstance(start_key, str):
        try:
            start_key = json.loads(start_key)
        except json.JSONDecodeError:
            start_key = None

    try:
        
        meta_res = table.get_item(Key={'product_id': str(product_id), 'entity_type': ENTITY_REVIEW_META})
        summary_data = meta_res.get('Item')
        if summary_data:
            summary_data = decimal_to_native(summary_data)
        else:
            summary_data = {
                "total_reviews": 0, "star_1": 0, "star_2": 0, "star_3": 0, "star_4": 0, "star_5": 0
            }


        total_stars = sum([summary_data.get(f"star_{i}", 0) * i for i in range(1, 6)])
        total_reviews = summary_data.get("total_reviews", 0)
        avg_rating = round((total_stars / total_reviews), 1) if total_reviews > 0 else 0


        query_kwargs = {
            "KeyConditionExpression": Key('product_id').eq(str(product_id)) & Key('entity_type').begins_with(ENTITY_REVIEW_PREFIX),
            "FilterExpression": Attr('status').eq("APPROVED") if not is_admin else Attr('status').exists(), # Admins see all, others see only APPROVED
            # Note: Sorting by time is not supported with current data model (sort key is entity_type, not created_at).
            # To enable time-based sorting, add a GSI with created_at as sort key.
            "ScanIndexForward": (sort_order == "asc"), # This sorts by entity_type lexicographically, not by time
            "Limit": limit
        }
        if start_key:
            query_kwargs["ExclusiveStartKey"] = start_key

        response = table.query(**query_kwargs)
        
        return {
            'statusCode': 200, 
            'body': {
                "summary": {
                    "average_rating": avg_rating,
                    "total_reviews": total_reviews,
                    "distribution": {
                        "5": summary_data.get("star_5", 0),
                        "4": summary_data.get("star_4", 0),
                        "3": summary_data.get("star_3", 0),
                        "2": summary_data.get("star_2", 0),
                        "1": summary_data.get("star_1", 0)
                    }
                },
                "reviews": decimal_to_native(response.get("Items", [])),
                "next_page_token": response.get("LastEvaluatedKey")
            }
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def update_review(body):
    """User updates their own review."""
    product_id = body.get("product_id")
    review_id = body.get("review_id")
    
    if not product_id or not review_id:
        return {'statusCode': 400, 'body': {"error": "product_id and review_id are required"}}

    update_fields = {}
    if "comment" in body: update_fields["comment"] = body["comment"].strip()
    if "media" in body: update_fields["media"] = body["media"]
    update_fields["updated_at"] = datetime.utcnow().isoformat()

    rating_changed = False
    old_rating = None
    new_rating = None
    if "rating" in body:
        new_rating = int(body.get("rating", 1))
        new_rating = max(1, min(5, new_rating))
        update_fields["rating"] = new_rating
        rating_changed = True

    if not update_fields:
        return {'statusCode': 400, 'body': {"error": "Nothing to update"}}

    # If rating is changing, get old rating and update summary
    if rating_changed:
        try:
            old_item = table.get_item(Key={'product_id': str(product_id), 'entity_type': f"{ENTITY_REVIEW_PREFIX}{review_id}"})
            if 'Item' not in old_item:
                return {'statusCode': 404, 'body': {"error": "Review not found"}}
            old_item = decimal_to_native(old_item['Item'])
            old_rating = old_item.get("rating")
            if old_rating:
                _update_review_summary(product_id, old_rating, is_addition=False)  # decrement old
            _update_review_summary(product_id, new_rating, is_addition=True)  # increment new
        except ClientError as e:
            return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

    update_expression = "SET "
    expr_names, expr_values = {}, {}

    for i, (key, value) in enumerate(update_fields.items()):
        update_expression += f"#k{i} = :v{i}, "
        expr_names[f"#k{i}"] = key
        expr_values[f":v{i}"] = value

    try:
        table.update_item(
            Key={'product_id': str(product_id), 'entity_type': f"{ENTITY_REVIEW_PREFIX}{review_id}"},
            UpdateExpression=update_expression.rstrip(", "),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=native_to_decimal(expr_values),
            ConditionExpression="attribute_exists(product_id)" # Must exist
        )
        return {'statusCode': 200, 'body': {"message": "Review updated successfully"}}
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
             return {'statusCode': 404, 'body': {"error": "Review not found"}}
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def interact_with_review(body, interaction_type="like"):
    """Handles both likes and dislikes atomically."""
    product_id = body.get("product_id")
    review_id = body.get("review_id")
    
    if not product_id or not review_id:
        return {'statusCode': 400, 'body': {"error": "product_id and review_id are required"}}

    field = "likes" if interaction_type == "like" else "dislikes"

    try:
        table.update_item(
            Key={'product_id': str(product_id), 'entity_type': f"{ENTITY_REVIEW_PREFIX}{review_id}"},
            UpdateExpression=f"ADD {field} :inc",
            ExpressionAttributeValues={":inc": 1},
            ConditionExpression="attribute_exists(product_id)"
        )
        return {'statusCode': 200, 'body': {"message": f"Review {field}d successfully"}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def admin_moderate_review(body):

    product_id = body.get("product_id")
    review_id = body.get("review_id")
    action = body.get("action", "HIDE").upper() # HIDE or DELETE or SHOW

    if not product_id or not review_id:
        return {'statusCode': 400, 'body': {"error": "product_id and review_id are required"}}

    try:
        if action == "DELETE":
            
            table.delete_item(Key={'product_id': str(product_id), 'entity_type': f"{ENTITY_REVIEW_PREFIX}{review_id}"})
            return {'statusCode': 200, 'body': {"message": "Review hard deleted"}}
        
        elif action == "SHOW":
            
            table.update_item(
                Key={'product_id': str(product_id), 'entity_type': f"{ENTITY_REVIEW_PREFIX}{review_id}"},
                UpdateExpression="SET #s = :status",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":status": "APPROVED"},
                ConditionExpression="attribute_exists(product_id)"
            )
            return {'statusCode': 200, 'body': {"message": "Review made visible"}}
        else:
            
            table.update_item(
                Key={'product_id': str(product_id), 'entity_type': f"{ENTITY_REVIEW_PREFIX}{review_id}"},
                UpdateExpression="SET #s = :status",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":status": "HIDDEN"},
                ConditionExpression="attribute_exists(product_id)"
            )
            return {'statusCode': 200, 'body': {"message": "Review hidden from public view"}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def get_admin_reviews(query_params):
    return get_product_reviews(query_params, is_admin=True)