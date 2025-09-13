"""
Lambda function for the Artist Agent.

This function will be triggered to find and execute IMAGE contracts.
"""
import base64
import json
import uuid  # <-- ВИПРАВЛЕНО: Додано відсутній імпорт

import boto3
from botocore.exceptions import ClientError

# Initialize Bedrock Runtime client
bedrock_runtime = boto3.client(service_name="bedrock-runtime")


def handler(event, context):
    """
    Main handler for the Artist Agent.

    Accepts a prompt from the event and generates an image.
    """
    # The 'context' argument is unused in this simple function, which is acceptable.
    _ = context
    print(f"Artist Agent triggered with event: {json.dumps(event)}")

    try:
        prompt = event.get("prompt")
        if not prompt:
            raise ValueError("Input event must include a 'prompt' key.")

        image_bytes = generate_image(prompt)

        # Use a unique name for the file in the temporary directory
        file_path = f"/tmp/{uuid.uuid4()}.png"
        with open(file_path, "wb") as f:
            f.write(image_bytes)

        print(f"Successfully generated and saved image to {file_path}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Artist Agent successfully generated an image.",
                "image_path": file_path
            })
        }

    except (ClientError, ValueError) as e:
        print(f"Error during image generation: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def generate_image(prompt: str) -> bytes:
    """
    Invokes the Stability AI SDXL 1.0 model to generate an image.

    Args:
        prompt: The text prompt for image generation.

    Returns:
        The generated image as bytes.
    """
    model_id = "stability.stable-diffusion-xl-v1"

    request_body = {
        "text_prompts": [{"text": prompt}],
        "cfg_scale": 7,
        "seed": 42,
        "steps": 30,
        "style_preset": "digital-art",
        "height": 1024,
        "width": 1024
    }

    try:
        print(f"Invoking Bedrock model {model_id}...")
        response = bedrock_runtime.invoke_model(
            body=json.dumps(request_body),
            modelId=model_id,
            accept="application/json",
            contentType="application/json",
        )
        print("Successfully invoked model.")

        response_body = json.loads(response.get("body").read())
        artifact = response_body.get("artifacts")[0]
        base64_image = artifact.get("base64")

        if artifact.get("finishReason") == 'ERROR':
            raise ValueError("Image generation failed due to an error in the model.")

        print("Decoding base64 image...")
        image_bytes = base64.b64decode(base64_image)
        print("Successfully decoded image.")

        return image_bytes

    except ClientError as e:
        error_message = f"Could not invoke model {model_id}. Error: {e}"
        print(f"Bedrock API error: {e.response['Error']['Message']}")
        raise ValueError(error_message) from e

    except Exception as e:
        error_message = f"An unexpected error occurred in generate_image: {e}"
        print(error_message)
        raise ValueError(error_message) from e