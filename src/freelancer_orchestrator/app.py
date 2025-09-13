"""
Lambda function for the Freelancer Orchestrator.
This function is the "brain" that finds work on the marketplace and delegates
it to specialized agents for execution.
"""
import json
import os
import boto3
import requests
from botocore.exceptions import ClientError

# Initialize AWS clients
lambda_client = boto3.client("lambda")

# Get configuration from environment variables
API_BASE_URL = os.environ.get("API_BASE_URL")
ARTIST_AGENT_ARN = os.environ.get("ARTIST_AGENT_ARN")
COPYWRITER_AGENT_ARN = os.environ.get("COPYWRITER_AGENT_ARN")


def handler(event, context):
    """
    Main handler for the Freelancer Orchestrator.
    Triggered by EventBridge, it fetches open contracts and invokes agents.
    """
    _ = context
    print(f"Orchestrator triggered with event: {json.dumps(event)}")

    if not all([API_BASE_URL, ARTIST_AGENT_ARN, COPYWRITER_AGENT_ARN]):
        print("Error: Missing required environment variables.")
        # No need to raise an exception, just log and exit gracefully.
        return {"statusCode": 500, "body": "Configuration error."}

    try:
        # 1. Get open contracts from the marketplace API
        contracts = get_open_contracts()
        print(f"Found {len(contracts)} open contracts.")

        if not contracts:
            print("No open contracts to process.")
            return {"statusCode": 200, "body": "No open contracts found."}

        # 2. Iterate and delegate tasks to specialized agents
        delegated_tasks = 0
        for contract in contracts:
            delegate_task(contract)
            delegated_tasks += 1
        
        print(f"Successfully delegated {delegated_tasks} tasks.")
        return {
            "statusCode": 200,
            "body": f"Successfully delegated {delegated_tasks} tasks."
        }

    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"Error processing contracts: {e}")
        # Raising an exception will cause Lambda to retry if configured.
        raise e


def get_open_contracts() -> list:
    """Fetches the list of open contracts from the API."""
    contracts_url = f"{API_BASE_URL}/contracts"
    print(f"Fetching open contracts from: {contracts_url}")
    
    response = requests.get(contracts_url, timeout=10)
    response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
    
    data = response.json()
    if "contracts" not in data or not isinstance(data["contracts"], list):
        raise ValueError("Invalid format for contracts response.")
        
    return data["contracts"]


def delegate_task(contract: dict):
    """Invokes the appropriate agent for a given contract."""
    contract_id = contract.get("contract_id")
    contract_type = contract.get("contract_type")
    prompt = contract.get("description")

    if not all([contract_id, contract_type, prompt]):
        print(f"Skipping malformed contract: {contract}")
        return

    payload = {"prompt": prompt, "contract_id": contract_id}
    
    target_arn = None
    if contract_type == "IMAGE":
        target_arn = ARTIST_AGENT_ARN
    elif contract_type == "TEXT":
        target_arn = COPYWRITER_AGENT_ARN
    else:
        print(f"Unknown contract type '{contract_type}' for contract {contract_id}. Skipping.")
        return

    try:
        print(f"Delegating {contract_type} contract {contract_id} to {target_arn}")
        lambda_client.invoke(
            FunctionName=target_arn,
            InvocationType="Event",  # Asynchronous invocation
            Payload=json.dumps(payload)
        )
    except ClientError as e:
        print(f"Failed to invoke agent for contract {contract_id}. Error: {e}")
        # We log the error but don't stop the orchestrator for other contracts.