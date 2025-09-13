"""
Lambda function handler for generating S3 presigned URLs for uploads.
"""
import json
import os
import boto3
import uuid
from botocore.exceptions import ClientError

# Initialize S3 client
s3_client = boto3.client("s3")
BUCKET_NAME = os.environ.get("ARTIFACTS_BUCKET_NAME")

# Constants
URL_EXPIRATION_SECONDS = 300  # 5 minutes

def handler(event, context):
    """
    Handler for POST /submissions/upload-url endpoint.
    Generates a presigned URL for an agent to upload an image.
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        # Generate a unique key for the S3 object
        object_key = f"images/{uuid.uuid4()}.png"

        # Generate the presigned URL
        presigned_url = s3_client.generate_presigned_post(
            Bucket=BUCKET_NAME,
            Key=object_key,
            Fields={"Content-Type": "image/png"},
            Conditions=[{"Content-Type": "image/png"}],
            ExpiresIn=URL_EXPIRATION_SECONDS
        )

        response_body = {
            "upload_url_details": presigned_url,
            "object_key": object_key
        }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(response_body)
        }

    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Could not generate upload URL."})
        }