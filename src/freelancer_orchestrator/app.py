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

ANALYST_AGENT_ARN = os.environ.get("ANALYST_AGENT_ARN")

# Create a mapping from contract type to Agent ARN for easy extension
AGENT_MAPPING = {
    "IMAGE": os.environ.get("ARTIST_AGENT_ARN"),
    "TEXT": os.environ.get("COPYWRITER_AGENT_ARN"),
    "RESEARCH": ANALYST_AGENT_ARN
}


def handler(event, context):
    """
    Main handler for the Freelancer Orchestrator.
    Triggered by EventBridge, it fetches open contracts and invokes agents.
    """
    _ = context
    print(f"Orchestrator triggered with event: {json.dumps(event)}")

    # Validate that all required ARNs are configured
    if not all(AGENT_MAPPING.values()) or not API_BASE_URL:
        print("Error: Missing required environment variables.")
        return {"statusCode": 500, "body": "Configuration error."}

    try:
        contracts = get_open_contracts()
        print(f"Found {len(contracts)} open contracts.")

        if not contracts:
            print("No open contracts to process.")
            return {"statusCode": 200, "body": "No open contracts found."}

        delegated_tasks = delegate_tasks(contracts)
        
        print(f"Successfully delegated {delegated_tasks} tasks.")
        return {
            "statusCode": 200,
            "body": f"Successfully delegated {delegated_tasks} tasks."
        }

    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"Error processing contracts: {e}")
        raise e


def get_open_contracts() -> list:
    """Fetches the list of open contracts from the API."""
    contracts_url = f"{API_BASE_URL}/contracts"
    print(f"Fetching open contracts from: {contracts_url}")
    
    response = requests.get(contracts_url, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    if "contracts" not in data or not isinstance(data["contracts"], list):
        raise ValueError("Invalid format for contracts response.")
        
    return data["contracts"]


def delegate_tasks(contracts: list) -> int:
    """Iterates through contracts and invokes the appropriate agent for each."""
    delegation_count = 0
    for contract in contracts:
        contract_id = contract.get("contract_id")
        contract_type = contract.get("contract_type")
        prompt = contract.get("description")

        if not all([contract_id, contract_type, prompt]):
            print(f"Skipping malformed contract: {contract}")
            continue

        # This is the refactored contract selection logic
        target_arn = AGENT_MAPPING.get(contract_type)

        if not target_arn:
            print(f"Unknown contract type '{contract_type}' for contract {contract_id}. Skipping.")
            continue

        try:
            payload = {"prompt": prompt, "contract_id": contract_id}
            print(f"Delegating {contract_type} contract {contract_id} to {target_arn}")
            lambda_client.invoke(
                FunctionName=target_arn,
                InvocationType="Event",
                Payload=json.dumps(payload)
            )
            delegation_count += 1
        except ClientError as e:
            print(f"Failed to invoke agent for contract {contract_id}. Error: {e}")

    return delegation_count