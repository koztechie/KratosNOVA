"""
Lambda function for the Copywriter Agent.
This function is invoked by the orchestrator to execute TEXT contracts.
"""
import json
import os
import boto3
import requests
import uuid
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

    try:
        prompt = event.get("prompt")
        contract_id = event.get("contract_id")
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
    # ... (код цієї функції залишається БЕЗ ЗМІН)
    for attempt in range(max_retries):
        generated_text = generate_text(prompt)
        try:
            start_index = generated_text.find('[')
            end_index = generated_text.rfind(']')
            if start_index != -1 and end_index != -1:
                json_str = generated_text[start_index:end_index+1]
                parsed_json = json.loads(json_str)
                if isinstance(parsed_json, list): return parsed_json
        except json.JSONDecodeError: continue
    raise ValueError(f"Failed to get a valid JSON array from the model after {max_retries} attempts.")

def generate_text(prompt: str) -> str:
    # ... (код цієї функції залишається БЕЗ ЗМІН)
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    request_body = { "anthropic_version": "bedrock-2023-05-31", "max_tokens": 1024, "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]}
    try:
        response = bedrock_runtime.invoke_model(body=json.dumps(request_body), modelId=model_id, accept="application/json", contentType="application/json")
        response_body = json.loads(response.get("body").read())
        return response_body.get("content")[0].get("text")
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