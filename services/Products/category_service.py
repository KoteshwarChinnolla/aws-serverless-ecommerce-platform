import boto3
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
from common import table, decimal_to_native, short_product
ENTITY_META = "CATEGORY_META"

def store_category_metadata(body):
    category_name = body.get("category", "").lower()
    if not category_name:
        return {'statusCode': 400, 'body': {"error": "Category name is required"}}

    meta_id = f"META#{category_name}"
    
    item = {
        **body,
        "product_id": meta_id,
        "entity_type": ENTITY_META,  # SORT KEY
        "category": category_name,
        "updated_at": datetime.utcnow().isoformat()
    }

    try:
        table.put_item(Item=item)
        return {'statusCode': 200, 'body': {"message": f"Metadata for {category_name} updated."}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def update_category_metadata(body):
    category_name = body.get('category')
    if not category_name:
        return {'statusCode': 400, 'body': {"error": 'category name is required'}}

    meta_id = f"META#{category_name.lower()}"
    body['updated_at'] = datetime.utcnow().isoformat()
    
    update_fields = {k: v for k, v in body.items() if k not in ['product_id', 'entity_type', 'category', 'created_at']}
    
    if not update_fields:
         return {'statusCode': 400, 'body': {"error": 'No fields to update'}}

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
        table.update_item(
            Key={'product_id': meta_id, "entity_type": ENTITY_META}, 
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="UPDATED_NEW"
        )
        return {'statusCode': 200, 'body': {"message": 'Category metadata updated successfully'}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def delete_category_metadata(category_name):
    if not category_name:
        return {'statusCode': 400, 'body': {"error": 'category query param is required'}}
        
    meta_id = f"META#{category_name.lower()}"
    
    try:
        table.delete_item(
            Key={"product_id": meta_id, "entity_type": ENTITY_META},
            ConditionExpression="attribute_exists(product_id)"
        )
        return {'statusCode': 200, 'body': {"message": f'Category metadata for {category_name} deleted successfully'}}
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
             return {'statusCode': 404, 'body': {"error": 'Category metadata not found'}}
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def get_products_by_category(category):
    """Utilizes the Global Secondary Index to quickly fetch products by category."""
    if not category:
        return {"statusCode": 400, "body": {"error": "category is required"}}

    try:
        response = table.query(
            IndexName="category_index",
            KeyConditionExpression=Key("category").eq(category.lower())
        )
        
        # Split actual products from the metadata row
        items = response.get("Items", [])
        products = [short_product(item) for item in items if not item.get("is_metadata")]
        metadata = next((item for item in items if item.get("is_metadata")), None)

        return {
            "statusCode": 200, 
            "body": {
                "metadata": decimal_to_native(metadata),
                "count": len(products),
                "products": decimal_to_native(products)
            }
        }
    except Exception as e:
        return {"statusCode": 500, "body": {"error": str(e)}}

def find_unique_categories():
    try:
        response = table.scan(
            ProjectionExpression="#cat",
            ExpressionAttributeNames={"#cat": "category"}
        )
        items = response.get("Items", [])
        categories = list({item["category"] for item in items if "category" in item})

        return {"statusCode": 200, "body": {"categories": categories}}
    except ClientError as e:
        return {"statusCode": 500, "body": {"error": e.response["Error"]["Message"]}}
    

def get_all_categories_with_metadata():
    try:
        response = table.scan(
            FilterExpression=Attr("entity_type").eq(ENTITY_META)
        )
        items = response.get("Items", [])
        categories_meta = {item["category"]: decimal_to_native(item) for item in items if "category" in item}

        return {"statusCode": 200, "body": {"categories_meta": categories_meta}}
    except ClientError as e:
        return {"statusCode": 500, "body": {"error": e.response["Error"]["Message"]}}