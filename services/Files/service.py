import boto3
import base64
import uuid
import mimetypes
import json
import os

import os
import mimetypes
import uuid
import boto3

# FIXED: Changed os.getenv keys to match the CloudFormation YAML
S3_BUCKET = os.getenv("S3_BUCKET", "prodect-management-app-files")
S3_REGION = os.getenv("S3_REGION", "ap-south-1")

def upload_url(body):
    name = body.get("name", "unknown").replace(" ", "_")
    doc_name = body.get("doc_name", "file").replace(" ", "_")
    content_type = body.get("contentType", "application/octet-stream")
    print(f"Received request to upload file: {doc_name} with content type: {content_type} for user: {name} uploading to bucket: {S3_BUCKET} in region: {S3_REGION}")
    extension = mimetypes.guess_extension(content_type)

    if not extension:
        extension = ""

    key = f"{name}/{doc_name}_{uuid.uuid4()}{extension}"

    s3 = boto3.client("s3", region_name=S3_REGION)

    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": S3_BUCKET,
            "Key": key,
            "ContentType": content_type
        },
        ExpiresIn=300
    )

    print(f"Generated upload URL: {upload_url}")

    return {
        "upload_url": upload_url,
        "key": key,
        "content_type": content_type
    }

def get_presigned_url(key):
    s3 = boto3.client('s3', region_name=S3_REGION)
    if key=="":
        return ""
    url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': S3_BUCKET, 'Key': key},
        ExpiresIn=604000
    )
    return {
        "url": url
    }

def delete_file(key):
    s3 = boto3.client('s3', region_name=S3_REGION)
    s3.delete_object(Bucket=S3_BUCKET, Key=key)
    return {
        "deleted": True
        }

