"""
Lambda function for the Copywriter Agent.
This function will be triggered to find and execute TEXT contracts.
"""
import json
import boto3
from botocore.exceptions import ClientError

# Initialize Bedrock Runtime client
bedrock_runtime = boto3.client(service_name="bedrock-runtime")


def handler(event, context):
    """
    Main handler for the Copywriter Agent.
    For now, it performs a test generation of text.
    """
    # The 'context' argument is unused in this simple function, which is acceptable.
    _ = context
    print(f"Copywriter Agent triggered with event: {json.dumps(event)}")

    # For this test, we use a hardcoded prompt.
    # Later, this will be taken from a DynamoDB contract.
    test_prompt = "Generate 5 short, catchy slogans for an AI project named KratosNOVA, which is a competitive marketplace for AI agents. Return ONLY a JSON array of strings."
    
    try:
        # 1. Generate the text using a helper function
        generated_text = generate_text(test_prompt)
        
        # The generated_text should be a JSON string, let's parse it to be sure
        slogans = json.loads(generated_text)
        
        print(f"Successfully generated slogans: {slogans}")

        # This is a temporary success response for testing purposes.
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Copywriter Agent successfully generated text.",
                "slogans": slogans
            })
        }

    except (ClientError, ValueError, json.JSONDecodeError) as e:
        print(f"Error during text generation: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def generate_text(prompt: str) -> str:
    """
    Invokes the Anthropic Claude 3 Haiku model to generate text.
    Args:
        prompt: The text prompt for text generation.
    Returns:
        The generated text as a string.
    """
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    
    # See https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html
    # for Claude 3 parameters.
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }

    try:
        print(f"Invoking Bedrock model {model_id}...")
        response = bedrock_runtime.invoke_model(
            body=json.dumps(request_body),
            modelId=model_id,
            accept="application/json",
            contentType="application/json"
        )
        print("Successfully invoked model.")

        response_body = json.loads(response.get("body").read())
        
        # The response from Claude 3 contains the text in the 'content' block
        generated_text = response_body.get("content")[0].get("text")
        print(f"Generated text: {generated_text}")

        return generated_text

    except ClientError as e:
        error_message = f"Could not invoke model {model_id}. Error: {e}"
        print(f"Bedrock API error: {e.response['Error']['Message']}")
        raise ValueError(error_message) from e
    except Exception as e:
        error_message = f"An unexpected error occurred in generate_text: {e}"
        print(error_message)
        raise ValueError(error_message) from e