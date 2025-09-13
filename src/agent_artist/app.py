"""
Lambda function for the Artist Agent.
This function is invoked by the orchestrator to execute IMAGE contracts.
"""
import base64
import json
import uuid
import boto3
import requests
from botocore.exceptions import ClientError

# Initialize AWS clients
bedrock_runtime = boto3.client(service_name="bedrock-runtime")
s3_client = boto3.client("s3")

# Get config from environment variables
API_BASE_URL = os.environ.get("API_BASE_URL")
ARTIFACTS_BUCKET_NAME = os.environ.get("ARTIFACTS_BUCKET_NAME")


def handler(event, context):
    """
    Main handler for the Artist Agent.
    Receives a contract, generates an image, uploads it to S3,
    and submits the result to the marketplace API.
    """
    _ = context
    print(f"Artist Agent triggered with event: {json.dumps(event)}")

    try:
        prompt = event.get("prompt")
        contract_id = event.get("contract_id")
        if not prompt or not contract_id:
            raise ValueError("Input event must include 'prompt' and 'contract_id'.")
        
        # 1. Generate the image
        print("Step 1: Generating image...")
        image_bytes = generate_image(prompt)

        # 2. Upload the image to S3
        print("Step 2: Uploading image to S3...")
        object_key = f"images/{contract_id}-{uuid.uuid4()}.png"
        s3_client.put_object(
            Bucket=ARTIFACTS_BUCKET_NAME,
            Key=object_key,
            Body=image_bytes,
            ContentType="image/png"
        )
        print(f"Successfully uploaded to s3://{ARTIFACTS_BUCKET_NAME}/{object_key}")

        # 3. Submit the result to the marketplace
        print("Step 3: Submitting result to marketplace...")
        submit_work(contract_id, object_key)
        print("Submission successful.")

        return {"status": "success"} # Simple response for async invocation

    except (ClientError, ValueError, requests.exceptions.RequestException) as e:
        print(f"Artist Agent failed for contract {contract_id}. Error: {e}")
        # In async invocation, there's no one to see the return, but we log the error.
        # For production, you'd add this failed task to a Dead Letter Queue (DLQ).
        raise e


def generate_image(prompt: str) -> bytes:
    # ... (код цієї функції залишається БЕЗ ЗМІН)
    model_id = "stability.stable-diffusion-xl-v1"
    request_body = { "text_prompts": [{"text": prompt}], "cfg_scale": 7, "seed": 42, "steps": 30, "style_preset": "digital-art", "height": 1024, "width": 1024 }
    try:
        response = bedrock_runtime.invoke_model( body=json.dumps(request_body), modelId=model_id, accept="application/json", contentType="application/json")
        response_body = json.loads(response.get("body").read())
        artifact = response_body.get("artifacts")[0]
        if artifact.get("finishReason") == 'ERROR': raise ValueError("Image generation failed in model.")
        base64_image = artifact.get("base64")
        return base64.b64decode(base64_image)
    except Exception as e:
        raise ValueError(f"Error in generate_image: {e}") from e

        
def submit_work(contract_id: str, submission_data: str):
    """Submits the completed work via the API."""
    submission_url = f"{API_BASE_URL}/contracts/{contract_id}/submissions"
    payload = {
        "agent_id": f"agent-artist-{uuid.uuid4()}", # Generate a unique ID for this instance
        "submission_data": submission_data
    }
    print(f"Submitting to {submission_url} with payload: {json.dumps(payload)}")
    response = requests.post(submission_url, json=payload, timeout=10)
    response.raise_for_status()
    print(f"Submission API response: {response.json()}")