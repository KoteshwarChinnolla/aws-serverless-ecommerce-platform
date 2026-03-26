import json
import boto3
import bcrypt
import random
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key, Attr
import uuid
import os
from jwt import PyJWKClient
import jwt


GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUER = "https://accounts.google.com"

jwk_client = PyJWKClient(GOOGLE_JWKS_URL)

USERS_TABLE = os.environ.get("USERS_TABLE", "users")

JWT_SECRET = os.environ.get("JWT_SECRET", "CHANGE_ME_TO_STRONG_SECRET")
JWT_ALGO = os.environ.get("JWT_ALGO", "HS256")
ACCESS_TOKEN_DAYS = int(os.environ.get("ACCESS_TOKEN_DAYS", 1))
REFRESH_TOKEN_DAYS = int(os.environ.get("REFRESH_TOKEN_DAYS", 7))
MAX_OTP_PER_HOUR = int(os.environ.get("MAX_OTP_PER_HOUR", 5))

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "285383883957-dkp2fsji75gb54ej86r9ui4s0h4cg9te.apps.googleusercontent.com")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(USERS_TABLE)

def generate_tokens_for_days(days):
    """Unified helper to create both access and refresh tokens."""
    
    jti = str(uuid.uuid4())

    payload = {
        "iat": int(datetime.utcnow().timestamp()),
        "jti": jti
    }
    acc_payload = payload.copy()
    acc_payload["exp"] = int((datetime.utcnow() + timedelta(days=days)).timestamp())
    access_token = jwt.encode(acc_payload, JWT_SECRET, algorithm=JWT_ALGO)
    
    
    return {
        "access_token": access_token
    }

# --- UTILS ---
def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  # Required for frontend to read the response
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT,DELETE"
        },
        "body": json.dumps(body, default=str)
    }


def hash_password(password: str) -> str:
    try:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except Exception as e:
        print("HASH ERROR:", e)
        return None

def generate_tokens(user_item):
    """Unified helper to create both access and refresh tokens."""
    # Payload includes useful details for the frontend
    print(f"Generating tokens for user: {user_item.get('email')}, role: {user_item.get('role')}")
    jti = str(uuid.uuid4())

    payload = {
        "email": user_item.get("email"),
        "name": user_item.get("name", "User"),
        "role": user_item.get("role", "USER"),
        "iat": int(datetime.utcnow().timestamp()),
        "jti": jti
    }
    

    acc_payload = payload.copy()
    acc_payload["exp"] = int((datetime.utcnow() + timedelta(days=ACCESS_TOKEN_DAYS)).timestamp())
    access_token = jwt.encode(acc_payload, JWT_SECRET, algorithm=JWT_ALGO)
    print("Generated access token with jti:", jti)
    

    ref_payload = payload.copy()
    ref_payload["exp"] = int((datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS)).timestamp())
    refresh_token = jwt.encode(ref_payload, JWT_SECRET, algorithm=JWT_ALGO)
    print("Generated refresh token with jti:", jti)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "email": payload["email"],
            "name": payload["name"],
            "role": payload["role"],
            "profile": user_item.get("profile", ""),
        }
    }

def register(body):
    print(body)
    email = body.get("email")
    password = body.get("password")

    
    if not email or not password:
        return response(400, {"error": "Email and password required"})


    if "Item" in table.get_item(Key={"PK": f"USER#{email}", "SK": "PROFILE"}):
        return response(400, {"error": "User already exists"})

    print("CHECK 1")
    password_new = ""
    if(password=="RANDOM_PASSWORD"):
        letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i in range(10):
            password_new += random.choice(letters)
    else:
        password_new = password
    print("registering user with email:", email)
    user_item = {
        "PK": f"USER#{email}",
        "SK": "PROFILE",
        "email": email,
        "name": body.get("name", "New User"),
        "password_hash": bcrypt.hashpw(password_new.encode(), bcrypt.gensalt()).decode(),
        "role": body.get("role", "USER"),
        "profile": body.get("profile", ""),
        "status": "ACTIVE",
        "created_at": datetime.utcnow().isoformat()
    }

    table.put_item(Item=user_item)
    return response(201, {"name": body.get("name", "New User"), "email": email, "password": password_new, "role": body.get("role", "USER")})

def get_user_by_email(email):
    if not email:
        return None
    res = table.get_item(Key={"PK": f"USER#{email}", "SK": "PROFILE"})
    return response(200, res.get("Item"))

def login_password(body, is_google=False):
    email = body.get("email")
    password = body.get("password")

    if not email or not password:
        return response(400, {"error": "Email and password required"})
    
    res = table.get_item(Key={"PK": f"USER#{email}", "SK": "PROFILE"})
    user = res.get("Item")
    print(user)
    
    if not user:
        return response(401, {"error": "User not found"})
    
    if not is_google and not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return response(401, {"error": "Incorrect password"})

    return response(200, generate_tokens(user))

def google_oauth_login(body):
    id_token = body.get("token")
    if not id_token:
        return response(400, {"error": "Google ID token required"})

    try:
        signing_key = jwk_client.get_signing_key_from_jwt(id_token)

        decoded = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=GOOGLE_CLIENT_ID,
            issuer=GOOGLE_ISSUER
        )

        email = decoded["email"]
        name = decoded.get("name", "Google User")
        google_sub = decoded["sub"]

        res = table.get_item(Key={"PK": f"USER#{email}", "SK": "PROFILE"})
        user = res.get("Item")

        if not user:
            user = {
                "PK": f"USER#{email}",
                "SK": "PROFILE",
                "email": email,
                "name": name,
                "role": "USER",
                "auth_provider": "google",
                "provider_id": google_sub,
                "created_at": datetime.utcnow().isoformat()
            }
            table.put_item(Item=user)

        return response(200, generate_tokens(user))

    except jwt.ExpiredSignatureError:
        return response(401, {"error": "Google token expired"})

    except jwt.InvalidTokenError:
        return response(401, {"error": "Invalid Google token"})

    except Exception as e:
        print("Google OAuth error:", e)
        return response(500, {"error": "OAuth login failed"})
    
def send_otp_verify(body):
    email = body.get("email")
    if not email: 
        return response(400, {"error": "Email required"})


    now = datetime.utcnow()
    one_hour_ago = (now - timedelta(hours=1)).isoformat()

    recent_otps = table.query(
        KeyConditionExpression=Key("PK").eq(f"OTP#{email}") & Key("SK").gt(one_hour_ago)
    )
    
    if len(recent_otps.get("Items", [])) >= MAX_OTP_PER_HOUR:
        return response(429, {"error": "Too many OTP requests. Try again later."})

    active_otps = table.query(
        KeyConditionExpression=Key("PK").eq(f"OTP#{email}"),
        FilterExpression=Attr("status").eq("ACTIVE")
    )
    
    for item in active_otps.get("Items", []):
        table.update_item(
            Key={"PK": f"OTP#{email}", "SK": item["SK"]},
            UpdateExpression="SET #s = :inactive",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":inactive": "INACTIVE"}
        )

    otp_code = str(random.randint(100000, 999999))
    expiry_timestamp = int((now + timedelta(minutes=10)).timestamp())
    
    new_otp_item = {
        "PK": f"OTP#{email}",
        "SK": now.isoformat(),
        "email": email,
        "otp": otp_code,
        "ttl": expiry_timestamp,
        "status": "ACTIVE"
    }
    
    table.put_item(Item=new_otp_item)

    # 5. Send via Brevo
    try:
        print(f"OTP for {email}: {otp_code}")
        return response(200, {"email": email, "otp": otp_code})
    except Exception as e:
        print(f"Mail Error: {e}")
        return response(500, {"error": "Failed to send email"})


def request_otp(body):
    email = body.get("email")
    if not email: 
        return response(400, {"error": "Email required"})
    
    # 1. Verify user exists
    user_res = table.get_item(Key={"PK": f"USER#{email}", "SK": "PROFILE"})
    if "Item" not in user_res:
        return response(404, {"error": "User not found"})

    now = datetime.utcnow()
    one_hour_ago = (now - timedelta(hours=1)).isoformat()

    recent_otps = table.query(
        KeyConditionExpression=Key("PK").eq(f"OTP#{email}") & Key("SK").gt(one_hour_ago)
    )
    
    if len(recent_otps.get("Items", [])) >= MAX_OTP_PER_HOUR:
        return response(429, {"error": "Too many OTP requests. Try again later."})

    active_otps = table.query(
        KeyConditionExpression=Key("PK").eq(f"OTP#{email}"),
        FilterExpression=Attr("status").eq("ACTIVE")
    )
    
    for item in active_otps.get("Items", []):
        table.update_item(
            Key={"PK": f"OTP#{email}", "SK": item["SK"]},
            UpdateExpression="SET #s = :inactive",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":inactive": "INACTIVE"}
        )

    # 4. Generate New OTP
    otp_code = str(random.randint(100000, 999999))
    expiry_timestamp = int((now + timedelta(minutes=10)).timestamp())
    
    new_otp_item = {
        "PK": f"OTP#{email}",
        "SK": now.isoformat(),
        "email": email,
        "otp": otp_code,
        "ttl": expiry_timestamp,
        "status": "ACTIVE"
    }
    
    table.put_item(Item=new_otp_item)

    # 5. Send via Brevo
    try:
        print(f"OTP for {email}: {otp_code}")
        return response(200, {"email": email, "otp": otp_code})
    except Exception as e:
        print(f"Mail Error: {e}")
        return response(500, {"error": "Failed to send email"})

def verify_otp_login(body):
    email = body.get("email")
    otp_provided = body.get("otp")
    
    # Query the most recent ACTIVE OTP
    res = table.query(
        KeyConditionExpression=Key("PK").eq(f"OTP#{email}"),
        FilterExpression=Attr("status").eq("ACTIVE"),
        ScanIndexForward=False, # Gets latest first
        Limit=1
    )
    
    items = res.get("Items", [])
    if not items:
        return response(401, {"error": "No active OTP found"})

    otp_item = items[0]
    
    # Security Validation
    if otp_item["otp"] != otp_provided:
        return response(401, {"error": "Invalid OTP"})
    
    if int(datetime.utcnow().timestamp()) > otp_item["ttl"]:
        return response(401, {"error": "OTP has expired"})

    # Success: Mark as INACTIVE (Used)
    table.update_item(
        Key={"PK": f"OTP#{email}", "SK": otp_item["SK"]},
        UpdateExpression="SET #s = :used",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":used": "INACTIVE"}
    )

    
    user_res = table.get_item(Key={"PK": f"USER#{email}", "SK": "PROFILE"})
    return response(200, generate_tokens(user_res.get("Item")))

def refresh_token(body):
    token = body.get("refresh_token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        # We fetch the user again to ensure role/status hasn't changed
        user_res = table.get_item(Key={"PK": f"USER#{payload['email']}", "SK": "PROFILE"})
        return response(200, generate_tokens(user_res.get("Item")))
    except:
        return response(401, {"error": "Invalid or expired refresh token"})

def delete(body):
    email = body.get("email")
    if not email:
        return response(400, {"error": "email required"})
    table.delete_item(Key={"PK": f"USER#{email}", "SK": "PROFILE"})
    return response(200, {"message": "Admin deleted successfully"})

def update(body):
    email = body.get("email")
    updates = {k: v for k, v in body.items() if k != "email"}

    if not email:
        return response(400, {"error": "email required"})
    
    if not updates:
        return response(400, {"error": "No update fields provided"})

    if "password" in updates:
        updates["password_hash"] = hash_password(updates.pop("password"))

    update_expr = "SET " + ", ".join([f"#{k} = :{k}" for k in updates.keys()])
    attr_names = {f"#{k}": k for k in updates.keys()}
    attr_values = {f":{k}": v for k, v in updates.items()}

    try:
        table.update_item(
            Key={"PK": f"USER#{email}", "SK": "PROFILE"},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values
        )
        return response(200, {"message": "User updated successfully"})
    except Exception as e:
        print(f"Update Error: {e}")
        return response(500, {"error": str(e)})

def get_users_by_role(role):
    try:
        db_response = table.scan(
            FilterExpression=Attr("role").eq(role) & Attr("SK").eq("PROFILE")
        )
        users = db_response.get("Items", [])
        return response(200, {f"{role.lower()}s": users})
    except Exception as e:
        print(f"Scan Error: {e}")
        return response(500, {"error": str(e)})


def logout(headers):
    token = headers.get("authorization", "").split(" ")[-1]
    print("auth token " +token)

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=["HS256"]
    )

    jti = payload["jti"]
    exp = payload["exp"]

    table.put_item(
        Item={
            "PK": f"REVOKED_TOKEN#{jti}",
            "SK": "REVOKED_TOKEN",
            "ttl": exp
        }
    )
    return response(200, {"message": "Logged out successfully"})