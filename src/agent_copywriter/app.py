"""
Lambda function for the Copywriter Agent.
This function is invoked by the orchestrator to execute TEXT contracts.
"""
import json
import os
import uuid
import boto3
import requests
from botocore.exceptions import ClientError

# Initialize clients
bedrock_runtime = boto3.client(service_name="bedrock-runtime")
API_BASE_URL = os.environ.get("API_BASE_URL")

def handler(event, context):
    """
    Main handler for the Copywriter Agent.
    Receives a contract, generates text, and submits the result.
    """
    _ = context
    print(f"Copywriter Agent triggered with event: {json.dumps(event)}")

    contract_id = event.get("contract_id") # Get contract_id early for error logging
    try:
        prompt = event.get("prompt")
        if not prompt or not contract_id:
            raise ValueError("Input event must include 'prompt' and 'contract_id'.")

        # 1. Generate the text
        print("Step 1: Generating text...")
        slogans = generate_and_parse_slogans(prompt)
        # We submit the first slogan as an example
        submission_text = slogans[0] if slogans else "No slogan generated."

        # 2. Submit the result to the marketplace
        print("Step 2: Submitting result to marketplace...")
        submit_work(contract_id, submission_text)
        print("Submission successful.")
        
        return {"status": "success"}

    except (ClientError, ValueError, requests.exceptions.RequestException) as e:
        print(f"Copywriter Agent failed for contract {contract_id}. Error: {e}")
        raise e

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
            print(f"Failed to decode JSON from model response: '{generated_text}', retrying...")
            continue # Go to the next attempt
            
    raise ValueError(f"Failed to get a valid JSON array from the model after {max_retries} attempts.")

def generate_text(prompt: str) -> str:
    """
    Invokes the Anthropic Claude 3 Haiku model to generate text.
    """
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    
    # Hardened prompt to strictly enforce JSON output
    hardened_prompt = f"""
    You are an AI assistant that ONLY responds with JSON.
    Your task is to perform the user's request and format the entire output as a single, raw JSON object.
    Do not under any circumstances include any explanatory text, markdown, or any characters before or after the JSON object.

    User Request: "{prompt}"

    Your JSON response must be a JSON array of strings.
    """

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": [{"type": "text", "text": hardened_prompt}]}]
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
        print(f"Raw model output: {generated_text}")
        return generated_text
    except Exception as e:
        raise ValueError(f"Error in generate_text: {e}") from e

def submit_work(contract_id: str, submission_data: str):
    """Submits the completed work via the API."""
    submission_url = f"{API_BASE_URL}/contracts/{contract_id}/submissions"
    payload = {
        "agent_id": f"agent-copywriter-{uuid.uuid4()}",
        "submission_data": submission_data
    }
    print(f"Submitting to {submission_url} with payload: {json.dumps(payload)}")
    response = requests.post(submission_url, json=payload, timeout=10)
    response.raise_for_status()
    print(f"Submission API response: {response.json()}")