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
    _ = context
    print(f"Copywriter Agent triggered with event: {json.dumps(event)}")

    test_prompt = "Generate 5 short, catchy slogans for an AI project named KratosNOVA, which is a competitive marketplace for AI agents. Return ONLY a valid JSON array of strings, without any surrounding text or markdown."
    
    try:
        slogans = generate_and_parse_slogans(test_prompt)
        print(f"Successfully generated and parsed slogans: {slogans}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Copywriter Agent successfully generated text.",
                "slogans": slogans
            })
        }

    except (ClientError, ValueError) as e:
        print(f"Error during text generation: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def generate_and_parse_slogans(prompt: str, max_retries: int = 2) -> list:
    """
    Generates text and attempts to parse it as JSON, with retries.
    """
    for attempt in range(max_retries):
        print(f"Attempt {attempt + 1} of {max_retries} to generate and parse JSON.")
        generated_text = generate_text(prompt)
        try:
            # Attempt to find a JSON array within the response
            # This handles cases where the model adds text like "Here is the JSON:"
            start_index = generated_text.find('[')
            end_index = generated_text.rfind(']')
            if start_index != -1 and end_index != -1:
                json_str = generated_text[start_index:end_index+1]
                parsed_json = json.loads(json_str)
                if isinstance(parsed_json, list):
                    return parsed_json
        except json.JSONDecodeError:
            print("Failed to decode JSON, retrying...")
            continue # Go to the next attempt

    raise ValueError(f"Failed to get a valid JSON array from the model after {max_retries} attempts.")


def generate_text(prompt: str) -> str:
    """
    Invokes the Anthropic Claude 3 Haiku model to generate text.
    """
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ]
    }

    try:
        response = bedrock_runtime.invoke_model(
            body=json.dumps(request_body),
            modelId=model_id,
            accept="application/json",
            contentType="application/json"
        )
        response_body = json.loads(response.get("body").read())
        generated_text = response_body.get("content")[0].get("text")
        print(f"Generated text: {generated_text}")
        return generated_text
    except ClientError as e:
        error_message = f"Could not invoke model {model_id}. Error: {e}"
        print(f"Bedrock API error: {e.response['Error']['Message']}")
        raise ValueError(error_message) from e