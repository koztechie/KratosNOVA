"""
Lambda function for generating S3 presigned URLs for uploads and downloads.
"""
import json
import os
import boto3
import uuid
from botocore.exceptions import ClientError

# Initialize S3 client
s3_client = boto3.client("s3")
BUCKET_NAME = os.environ.get("ARTIFACTS_BUCKET_NAME")
URL_EXPIRATION_SECONDS = 3600  # 1 hour

def handler(event, context):
    """
    Main handler that routes based on the HTTP method.
    - POST /submissions/upload-url: Generates a URL for uploading.
    - GET /submissions/download-url: Generates a URL for downloading/viewing.
    """
    http_method = event.get("httpMethod")
    if http_method == "POST":
        return generate_upload_url(event)
    if http_method == "GET":
        return generate_download_url(event)
    
    return {"statusCode": 405, "body": "Method Not Allowed"}


def generate_upload_url(event):
    """Generates a presigned URL for an agent to upload an image."""
    try:
        object_key = f"images/{uuid.uuid4()}.png"
        presigned_url = s3_client.generate_presigned_post(
            Bucket=BUCKET_NAME, Key=object_key,
            Fields={"Content-Type": "image/png"},
            Conditions=[{"Content-Type": "image/png"}],
            ExpiresIn=URL_EXPIRATION_SECONDS
        )
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"upload_url_details": presigned_url, "object_key": object_key})
        }
    except ClientError as e:
        return {"statusCode": 500, "body": json.dumps({"error": f"Could not generate upload URL: {e}"})}


def generate_download_url(event):
    """Generates a presigned URL for a client to view an image."""
    try:
        # Get the object key from the query string parameter
        query_params = event.get("queryStringParameters", {})
        object_key = query_params.get("key")
        if not object_key:
            raise ValueError("'key' query string parameter is required.")

        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': object_key},
            ExpiresIn=URL_EXPIRATION_SECONDS
        )
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"download_url": presigned_url})
        }
    except (ClientError, ValueError) as e:
        return {"statusCode": 500, "body": json.dumps({"error": f"Could not generate download URL: {e}"})}