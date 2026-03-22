import boto3
import uuid
import os
from datetime import datetime
from decimal import Decimal
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
from common import decimal_to_native

CARTS_TABLE = os.environ.get('CARTS_TABLE', 'carts')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(CARTS_TABLE)

ENTITY_META = "CART_META"

def create_or_update_cart(body):
    """Creates a new cart or updates its metadata."""
    cart_id = body.get("cart_id") or str(uuid.uuid4())
    
    item = {
        "cart_id": cart_id,
        "entity_type": ENTITY_META,
        "user_id": body.get("user_id"),
        "status": body.get("status", "active"),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    try:
        table.put_item(Item=item)
        return {'statusCode': 200, 'body': {"message": "Cart updated", "cart_id": cart_id}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}
    
def checkout_and_terminate_cart(body):
    """Links order details to a cart and marks it as terminated. Handles all edge cases."""
    cart_id = body.get("cart_id")
    order_id = body.get("order_id")
    final_total = body.get("final_total", 0)
    
    if not cart_id or not order_id:
        return {'statusCode': 400, 'body': {"error": "cart_id and order_id are required"}}
        
    try:
        cart_data = table.query(KeyConditionExpression=Key("cart_id").eq(cart_id))
        items = cart_data.get("Items", [])
        
        has_items = any(item["entity_type"].startswith("ITEM#") for item in items)
        if not has_items:
            return {'statusCode': 400, 'body': {"error": "Cannot checkout an empty cart"}}


        table.update_item(
            Key={'cart_id': cart_id, 'entity_type': ENTITY_META},
            UpdateExpression="SET #status = :new_status, updated_at = :time, order_id = :oid, final_total = :total",
            ExpressionAttributeNames={
                "#status": "status" 
            },
            ExpressionAttributeValues={
                ":new_status": "terminated",
                ":time": datetime.utcnow().isoformat(),
                ":oid": order_id,
                ":total": Decimal(str(final_total)),
                ":expected_status": "active"
            },
            ConditionExpression="attribute_exists(cart_id) AND #status = :expected_status"
        )
        
        return {'statusCode': 200, 'body': {
            "message": "Cart successfully linked to order and terminated",
            "order_id": order_id,
            "cart_id": cart_id
        }}
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
             return {'statusCode': 400, 'body': {"error": 'Cart is already terminated or does not exist.'}}
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}
    

def get_user_cart_history(user_id):
    """Fetches all carts (history) for a specific user."""
    if not user_id:
        return {'statusCode': 400, 'body': {"error": "user_id is required"}}
        
    try:
        response = table.query(
            IndexName='user_id_index',
            KeyConditionExpression=Key('user_id').eq(user_id) & Key('entity_type').eq(ENTITY_META)
        )
        carts = response.get('Items', [])
        
        # Sort by updated_at descending so the newest carts are first
        carts.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        return {'statusCode': 200, 'body': {"carts": decimal_to_native(carts)}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def get_active_cart_for_user(user_id):
    """Fetches the most recent 'active' cart for a user."""
    if not user_id:
        return {'statusCode': 400, 'body': {"error": "user_id is required"}}
        
    try:
        response = table.query(
            IndexName='user_id_index',
            KeyConditionExpression=Key('user_id').eq(user_id) & Key('entity_type').eq(ENTITY_META),
            FilterExpression=Attr('status').eq('active')
        )
        active_carts = response.get('Items', [])
        
        if not active_carts:
             return {'statusCode': 404, 'body': {"message": "No active cart found for this user"}}
             

        active_carts.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        recent_cart = active_carts[0]
        
        
        return get_cart_with_filters(recent_cart['cart_id'])
        
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def add_item_to_cart(cart_id, body):
    """Adds an item. If it exists, increments quantity (Edge Case Handled)."""
    product_id = body.get("product_id")
    quantity = int(body.get("quantity", 1))
    
    if not product_id or quantity <= 0:
        return {'statusCode': 400, 'body': {"error": "Valid product_id and quantity > 0 are required"}}
        
    entity_key = f"ITEM#{product_id}"
    
    try:
        # Atomic update: Adds quantity if exists, otherwise creates new item with all details
        table.update_item(
            Key={'cart_id': cart_id, 'entity_type': entity_key},
            UpdateExpression="""SET 
                product_name = if_not_exists(product_name, :name),
                price = if_not_exists(price, :price),
                image = if_not_exists(image, :image),
                updated_at = :updated_at
                ADD quantity :q""",
            ExpressionAttributeValues={
                ":name": body.get("product_name", "Unknown"),
                ":price": Decimal(str(body.get("price", 0))),
                ":image": body.get("image", ""),
                ":updated_at": datetime.utcnow().isoformat(),
                ":q": quantity
            },
            ReturnValues="UPDATED_NEW"
        )
        return {'statusCode': 200, 'body': {"message": "Item added successfully"}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def get_cart_with_filters(cart_id, filters=None):

    if not cart_id:
        return {'statusCode': 400, 'body': {"error": "cart_id is required"}}
        
    try:
        response = table.query(
            KeyConditionExpression=Key("cart_id").eq(cart_id)
        )
        items = response.get("Items", [])
        
        if not items:
            return {'statusCode': 404, 'body': {"error": "Cart not found"}}
            
        cart_meta = next((item for item in items if item["entity_type"] == ENTITY_META), {})
        cart_products = [item for item in items if item["entity_type"].startswith("ITEM#")]
        
        # Apply Filters (Edge case: Searching within a specific cart)
        if filters:
            if "name" in filters and filters["name"]:
                search_term = filters["name"].lower()
                cart_products = [p for p in cart_products if search_term in p.get("product_name", "").lower()]
            if "min_price" in filters and filters["min_price"]:
                cart_products = [p for p in cart_products if p.get("price", 0) >= Decimal(filters["min_price"])]
            if "max_price" in filters and filters["max_price"]:
                cart_products = [p for p in cart_products if p.get("price", 0) <= Decimal(filters["max_price"])]
        
        # Calculate totals dynamically
        total_items = sum(p.get("quantity", 0) for p in cart_products)
        total_price = sum(p.get("price", 0) * p.get("quantity", 0) for p in cart_products)
        
        return {'statusCode': 200, 'body': {
            "metadata": decimal_to_native(cart_meta),
            "summary": {"total_unique_items": len(cart_products), "total_quantity": total_items, "total_price": float(total_price)},
            "items": decimal_to_native(cart_products)
        }}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def update_item_quantity(cart_id, product_id, quantity):
    """Updates item quantity. If 0, removes the item (Edge Case Handled)."""
    if quantity <= 0:
        return remove_item_from_cart(cart_id, product_id)
        
    try:
        table.update_item(
            Key={'cart_id': cart_id, 'entity_type': f"ITEM#{product_id}"},
            UpdateExpression="SET quantity = :q, updated_at = :time",
            ConditionExpression="attribute_exists(cart_id)", # Must exist
            ExpressionAttributeValues={
                ":q": quantity,
                ":time": datetime.utcnow().isoformat()
            }
        )
        return {'statusCode': 200, 'body': {"message": "Quantity updated"}}
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
             return {'statusCode': 404, 'body': {"error": 'Item not found in cart'}}
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def remove_item_from_cart(cart_id, product_id):
    try:
        table.delete_item(
            Key={'cart_id': cart_id, 'entity_type': f"ITEM#{product_id}"}
        )
        return {'statusCode': 200, 'body': {"message": "Item removed from cart"}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

def clear_cart(cart_id):
    """Deletes all items and metadata associated with the cart."""
    try:
        response = table.query(KeyConditionExpression=Key("cart_id").eq(cart_id))
        items = response.get("Items", [])
        
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={
                    'cart_id': item['cart_id'],
                    'entity_type': item['entity_type']
                })
        return {'statusCode': 200, 'body': {"message": "Cart cleared successfully"}}
    except ClientError as e:
        return {'statusCode': 500, 'body': {"error": e.response['Error']['Message']}}

