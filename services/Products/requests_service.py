import uuid
import time
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
from common import table, decimal_to_native
from decimal import Decimal

ENTITY_REQUEST = "REQUEST"

def request_product(body):
    """Creates a new project request."""
    current_time = datetime.utcnow()
    product_id = body.get("product_id") or f"REQ#{uuid.uuid4()}"

    item = {
        **body,
        "product_id": product_id,
        "entity_type": ENTITY_REQUEST, # SORT KEY
        "category": body.get("category", "").lower(),
        "requested_by": body.get("requested_by", "unknown"),
        "status": "PENDING", # Track request workflow
        "created_at": current_time.isoformat(),
        "time": int(time.mktime(current_time.timetuple()) * 1000),
    }

    try:
        table.put_item(Item=item)
        return {'statusCode': 201, 'body': {"message": "Project requested successfully", "product_id": product_id}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def get_requested_projects_by_user(user_id):
    """Fetch all requests made by a specific user utilizing the GSI."""
    if not user_id:
        return {'statusCode': 400, 'body': {"error": 'Missing user_id parameter'}}

    try:
        response = table.query(
            IndexName="requested_by_index",  # Ensure your CloudFormation uses exactly this name
            KeyConditionExpression=Key("requested_by").eq(user_id)
        )
        items = [item for item in response.get("Items", []) if item.get("entity_type") == ENTITY_REQUEST]
        return {'statusCode': 200, 'body': {"requests": decimal_to_native(items)}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def search_requested_projects(filters=None):
    """Search/Filter strictly through items that are Requests."""
    filter_expression = Attr("entity_type").eq(ENTITY_REQUEST)
    
    if filters:
        if "product_id" in filters and filters["product_id"]:
            filter_expression &= Attr("product_id").eq(str(filters["product_id"]))

        if "category" in filters and filters["category"]:
            filter_expression &= Attr("category").eq(str(filters["category"].lower()))

        if "name" in filters and filters["name"]:
            filter_expression &= Attr("name").begins_with(str(filters["name"].lower()))

        if "location" in filters and filters["location"]:
            filter_expression &= Attr("location").begins_with(str(filters["location"].lower()))

        if "min_delivery_days" in filters and filters["min_delivery_days"]:
            filter_expression &= Attr("min_delivery_days").gte(Decimal(filters["min_delivery_days"]))

        if "max_delivery_days" in filters and filters["max_delivery_days"]:
            filter_expression &= Attr("max_delivery_days").lte(Decimal(filters["max_delivery_days"]))
        
        if "min_price" in filters and filters["min_price"]:
            filter_expression &= Attr("selling_price").gte(Decimal(filters["min_price"]))

        if "max_price" in filters and filters["max_price"]:
            filter_expression &= Attr("selling_price").lte(Decimal(filters["max_price"]))

    try:
        response = table.scan(FilterExpression=filter_expression)
        items = response.get('Items', [])
        return {'statusCode': 200, 'body': {"count": len(items), "requests": decimal_to_native(items)}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def update_requested_project(product_id, body):
    if not product_id:
        return {'statusCode': 400, 'body': {"error": 'product_id is required'}}

    body['updated_at'] = datetime.utcnow().isoformat()
    update_fields = {k: v for k, v in body.items() if k not in ['product_id', 'entity_type', 'created_at']}

    update_expression = "SET "
    expr_names, expr_values = {}, {}

    for i, (key, value) in enumerate(update_fields.items()):
        update_expression += f"#k{i} = :v{i}, "
        expr_names[f"#k{i}"] = key
        expr_values[f":v{i}"] = value

    try:
        table.update_item(
            Key={'product_id': product_id, 'entity_type': ENTITY_REQUEST},
            UpdateExpression=update_expression.rstrip(", "),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
        return {'statusCode': 200, 'body': {"message": 'Request updated successfully'}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def approve_requested_project(body):
    """Updates the request status to APPROVED."""
    product_id = body.get("product_id")
    approv
    if not product_id:
        return {'statusCode': 400, 'body': {"error": 'product_id is required'}}

    try:
        table.update_item(
            Key={'product_id': product_id, 'entity_type': ENTITY_REQUEST},
            UpdateExpression="SET #status = :val, updated_at = :time",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":val": "APPROVED", ":time": datetime.utcnow().isoformat()}
        )
        return {'statusCode': 200, 'body': {"message": 'Request approved successfully'}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}


def delete_requested_project(product_id):
    """Deletes a request based on partition and sort key."""
    try:
        table.delete_item(
            Key={"product_id": str(product_id), "entity_type": ENTITY_REQUEST},
            ConditionExpression="attribute_exists(product_id)"
        )
        return {'statusCode': 200, 'body': {"message": 'Request deleted successfully'}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}
