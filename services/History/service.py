import boto3
import time
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import json
import base64


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("order_tracking_history")

def now_iso():
    return datetime.utcnow().isoformat()

def now_ms():
    return str(time.time() * 1000)

def log_order_created(item, remarks="Order Placed Successfully", action="PLACED"):
    """Creates the initial tracking status for a new order."""
    user_id = item.get("user_id")
    product_id = item.get("product_id")
    name = item.get("name")
    email = item.get("email")
    price = item.get("price")
    address = item.get("address")
    
    if not user_id or not product_id:
        raise ValueError("user_id and product_id are required")

    new_item = {
        "user_id": user_id,
        "product_id": product_id,
        "name": name,
        "email": email,
        "price": price,
        "address": address,
        "stage_id": "ORDER_RECEIVED",
        "action": action,
        "remarks": remarks,
        "created_at": now_ms(),
        "updated_at": now_iso()
    }

    table.put_item(Item=new_item)
    return new_item

def get_order_timeline(user_id):
    """Fetches the entire tracking history for a user."""
    response = table.query(
        KeyConditionExpression=Key("user_id").eq(user_id)
    )
    return response.get("Items", [])

def update_order_stage(body):
    """Updates the stage of a single product/order."""
    required_fields = ["user_id", "product_id", "stage_id", "action"]
    for field in required_fields:
        if not body.get(field):
            return {"error": f"{field} is required"}, 400

    existing_entries = table.query(
        KeyConditionExpression=Key("user_id").eq(body["user_id"]),
        FilterExpression=Attr("stage_id").eq(body["stage_id"]) & Attr("product_id").eq(body["product_id"])
    ).get("Items", [])

    if existing_entries:
        return {
            "error": "Conflict", 
            "message": f"Product is already marked as '{body['stage_id']}' for this user."
        }, 409

    item = {
        **body,
        "user_id": body["user_id"],
        "product_id": body["product_id"],
        "stage_id": body["stage_id"],
        "updated_at": now_iso()
    }
    
    table.put_item(Item=item)

    return {
        "message": "Order stage updated successfully",
        "data": item
    }, 200



def update_order_stage_bulk(body):

    if "items" not in body:
        return {"error": "items field is required"}, 400

    if not isinstance(body["items"], list):
        return {"error": "items must be a list"}, 400

    if not body["items"]:
        return {"error": "items list cannot be empty"}, 400

    required_fields = ["user_id", "product_id", "stage_id", "action"]
    ALLOWED_ACTIONS = {"MOVED", "CANCELLED", "DELIVERED"}

    valid_items = []
    errors = []
    email_list = []
    stage_name = ""
    
    # Track items processed in this exact batch to prevent payload duplicates
    seen_in_batch = set() 

    for index, item in enumerate(body["items"]):
        missing = [f for f in required_fields if not item.get(f)]
        if missing:
            errors.append({"index": index, "error": f"Missing fields: {', '.join(missing)}"})
            continue

        if item["action"] not in ALLOWED_ACTIONS:
            errors.append({"index": index, "error": f"Invalid action: {item['action']}"})
            continue

        # --- PREVENT PAYLOAD DUPLICATES ---
        combo_key = (item["user_id"], item["stage_id"], item["product_id"])
        if combo_key in seen_in_batch:
            errors.append({"index": index, "error": "Duplicate entry found within the request payload."})
            continue

        # --- PREVENT DATABASE DUPLICATES ---
        existing_entries = table.query(
            KeyConditionExpression=Key("user_id").eq(item["user_id"]),
            FilterExpression=Attr("stage_id").eq(item["stage_id"]) & Attr("product_id").eq(item["product_id"])
        ).get("Items", [])

        if existing_entries:
            errors.append({"index": index, "error": f"Product already exists in stage '{item['stage_id']}'."})
            continue
        
        # If it passes both checks, it's valid
        seen_in_batch.add(combo_key)
        stage_name = item["stage_id"]
        valid_items.append({
            **item, 
            "action": "DELIVERED" if stage_name == "DELIVERED" else "MOVED", 
            "remark": f"Your order has successfully moved to: {item['stage_id']}", 
            "created_at": now_ms(), 
            "updated_at": now_iso()
        })
        
        email_list.append({'email': item['email'], 'name': item.get("name", "Customer")})
        
    if not valid_items:
        return {
            "error": "No valid items to process",
            "details": errors
        }, 400

    try:
        with table.batch_writer() as batch:
            for item in valid_items:
                batch.put_item(Item=item)

        print("Sending stage update mail to: ", email_list)
        print("For stage: ", stage_name)

        notifications = []

        for user in email_list:
            notification = {
                "name": user["name"],
                "email": user["email"],
                "order_id": "Multiple" if len(valid_items) > 1 else valid_items[0]["product_id"],
                "status_title": f"Order Update: {stage_name}",
                "status_message": f"Your items have reached the {stage_name} stage."
            }
            notifications.append(notification)

        return {
            "message": "Bulk order stage update completed",
            "summary": {
                "total_received": len(body["items"]),
                "successfully_processed": len(valid_items),
                "failed": len(errors),
                "notifications": len(notifications)
            },
            "errors": errors
          }, 200
    except Exception as e:
        return {
            "error": "Failed to process bulk update",
            "exception": str(e)
        }, 500



def decode_cursor(cursor):
    try:
        return json.loads(base64.b64decode(cursor).decode())
    except Exception:
        return None

def fetch_order_flow(query_params):
    """Used for searching and filtering the order tracking flow."""
    user_id = query_params.get("user_id", None)
    product_id = query_params.get("product_id", None)

    filterable_fields = ["stage_id", "action"]
    starts_with = ["name", "email"]
    filter_expression = None
    query_kwargs = {}

    if user_id:
        query_kwargs["KeyConditionExpression"] = Key("user_id").eq(user_id)
    elif product_id:
        query_kwargs["IndexName"] = "product_id-created_at-index"
        query_kwargs["KeyConditionExpression"] = Key("product_id").eq(product_id)
    else:
        return {"error": "user_id or product_id is required"}, 400

    for field in filterable_fields:
        if query_params.get(field):
            expr = Attr(field).eq(query_params[field])
            filter_expression = expr if not filter_expression else filter_expression & expr

    for field in starts_with:
        if query_params.get(field):
            expr = Attr(field).begins_with(query_params[field])
            filter_expression = expr if not filter_expression else filter_expression & expr

    if user_id and product_id:
        expr = Attr("product_id").eq(product_id)
        filter_expression = expr if not filter_expression else filter_expression & expr

    if filter_expression:
        query_kwargs["FilterExpression"] = filter_expression

    # Fetch a slightly larger limit to account for dropped duplicates
    limit = int(query_params.get("limit", 20))
    query_kwargs["Limit"] = limit + 10 

    if query_params.get("cursor"):
        cursor = decode_cursor(query_params["cursor"])
        if cursor:
            query_kwargs["ExclusiveStartKey"] = cursor

    response = table.query(**query_kwargs)
    raw_data = response.get("Items", [])

    # --- READ-PATH PROTECTION: De-duplicate entries ---
    unique_items = []
    seen_tracking = set()

    for item in raw_data:
        # Create a unique signature for this tracking state
        tracking_sig = (item.get("user_id"), item.get("stage_id"), item.get("product_id"))
        
        if tracking_sig not in seen_tracking:
            seen_tracking.add(tracking_sig)
            unique_items.append(item)
            
            # Stop if we hit the requested limit after de-duplication
            if len(unique_items) == limit:
                break
                
    return {
        "count": len(unique_items),
        "items": unique_items,
        "next_cursor": response.get("LastEvaluatedKey")
    }, 200

def fetch_stage_ids_by_product(query_params):
    """Fetches all distinct stages a specific product has gone through."""
    product_id = query_params.get("product_id")

    if not product_id:
        return {"error": "product_id is required"}, 400

    try:
        response = table.query(
            IndexName="product_id-created_at-index",
            KeyConditionExpression=Key("product_id").eq(product_id),
            FilterExpression=Attr("stage_id").exists() & Attr("stage_id").ne(None)
        )

        items = response.get("Items", [])
        seen = set()
        stage_ids = []
        
        for item in items:
            stage_id = item.get("stage_id")
            created_at = item.get("created_at")

            if stage_id and stage_id not in seen:
                seen.add(stage_id)
                stage_ids.append({
                    "stage_id": stage_id,
                    "time": created_at
                })
                
        return {
            "count": len(stage_ids),
            "stage_ids": stage_ids
        }, 200

    except Exception as e:
        return {"error": str(e)}, 500

def fetch_products_by_stage(query_params):
    """Fetches all products currently in a specific stage (e.g., 'Dispatched')."""
    stage_id = query_params.get("stage_id")

    if not stage_id:
        return {"error": "stage_id is required"}, 400

    try:
        response = table.query(
            IndexName="stage_id_index",
            KeyConditionExpression=Key("stage_id").eq(stage_id)
        )

        items = response.get("Items", [])
        seen = set()
        product_ids = []

        for item in items:
            product_id = item.get("product_id")
            created_at = item.get("created_at")

            if product_id and product_id not in seen:
                seen.add(product_id)
                product_ids.append({
                    "product_id": product_id,
                    "time": created_at
                })

        return {
            "count": len(product_ids),
            "product_ids": product_ids
        }, 200

    except Exception as e:
        return {"error": str(e)}, 500


def fetch_products_by_user_id(query_params):
    """Fetches all products a user has purchased."""
    user_id = query_params.get("user_id")

    if not user_id:
        return {"error": "user_id is required"}, 400

    try:
        response = table.query(
            IndexName="user_id-index",
            KeyConditionExpression=Key("user_id").eq(user_id)
        )

        items = response.get("Items", [])
        seen = set()
        product_ids = []

        for item in items:
            product_id = item.get("product_id")
            created_at = item.get("created_at")

            if product_id and product_id not in seen:
                seen.add(product_id)
                product_ids.append({
                    "product_id": product_id,
                    "time": created_at
                })

        return {
            "count": len(product_ids),
            "product_ids": product_ids
        }, 200

    except Exception as e:
        return {"error": str(e)}, 500

def get_all_addresses_by_user_id(user_id):
    """Retrieves a history of addresses used by the user."""
    if not user_id:
        return {"error": "user_id is required"}, 400

    try:
        response = table.query(
            IndexName="user_id-index",
            KeyConditionExpression=Key("user_id").eq(str(user_id)),
            Limit=10,        
            ScanIndexForward=False   # latest by time (desc)
        )

        items = response.get("Items", [])
        seen = set()
        addresses = []

        for item in items:
            address = item.get("address")
            created_at = item.get("created_at")

            if address and address not in seen:
                seen.add(address)
                addresses.append({
                    "address": address,
                    "time": created_at
                })

        return {
            "count": len(addresses),
            "addresses": addresses
        }, 200
    
    except Exception as e:
        return {"error": str(e)}, 500
    
