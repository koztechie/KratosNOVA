"""
Lambda function for the Analyst Agent.
This function is invoked by the orchestrator to execute RESEARCH contracts.
"""
import json
import os
import boto3
import requests
import uuid
from botocore.exceptions import ClientError

bedrock_runtime = boto3.client(service_name="bedrock-runtime")
API_BASE_URL = os.environ.get("API_BASE_URL")

def handler(event, context):
    """Main handler for the Analyst Agent."""
    _ = context
    print(f"Analyst Agent triggered with event: {json.dumps(event)}")
    
    contract_id = event.get("contract_id")
    try:
        prompt = event.get("prompt")
        if not prompt or not contract_id:
            raise ValueError("Input event must include 'prompt' and 'contract_id'.")

        print("Step 1: Performing analysis...")
        analysis_result = perform_analysis(prompt)

        print("Step 2: Submitting result to marketplace...")
        submit_work(contract_id, analysis_result)
        print("Submission successful.")
        
        return {"status": "success"}
    except (ClientError, ValueError, requests.exceptions.RequestException) as e:
        print(f"Analyst Agent failed for contract {contract_id}. Error: {e}")
        raise e

def perform_analysis(original_prompt: str) -> str:
    """Uses Claude 3 Haiku to perform a simulated market analysis."""
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    
    # We wrap the original prompt with instructions for the analyst persona
    analysis_prompt = f"""
    You are a senior Market Research Analyst. Your task is to provide a concise analysis based on the following request.
    Focus on defining the target audience, their key interests, and potential marketing channels.
    Keep the analysis to a few key bullet points.

    **Research Request:** "{original_prompt}"
    """
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": [{"type": "text", "text": analysis_prompt}]}]
    }
    
    try:
        response = bedrock_runtime.invoke_model(body=json.dumps(request_body), modelId=model_id)
        response_body = json.loads(response.get("body").read())
        return response_body.get("content")[0].get("text")
    except Exception as e:
        raise ValueError(f"Error in perform_analysis: {e}") from e

def submit_work(contract_id: str, submission_data: str):
    """Submits the completed work via the API."""
    submission_url = f"{API_BASE_URL}/contracts/{contract_id}/submissions"
    payload = {
        "agent_id": f"agent-analyst-{uuid.uuid4()}",
        "submission_data": submission_data
    }
    response = requests.post(submission_url, json=payload, timeout=10)
    response.raise_for_status()