"""
Lambda function for the Agent-Manager.
This function handles the POST /goals endpoint, deconstructs the user's goal
into actionable contracts, and puts them on the marketplace.
"""
import json
import os
import boto3
import uuid
from datetime import datetime, timezone
from botocore.exceptions import ClientError

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
bedrock_runtime = boto3.client(service_name="bedrock-runtime")

# Get config from environment variables
CONTRACTS_TABLE_NAME = os.environ.get("CONTRACTS_TABLE_NAME")
contracts_table = dynamodb.Table(CONTRACTS_TABLE_NAME)


def handler(event, context):
    """
    Main handler for the Agent-Manager.
    """
    _ = context
    print(f"Agent-Manager triggered with event: {json.dumps(event)}")

    try:
        body = json.loads(event.get("body", "{}"))
        user_goal = body.get("description")
        if not user_goal:
            raise ValueError("Request body must include a 'description' for the goal.")

        # 1. Deconstruct the goal into contracts using Bedrock
        print(f"Deconstructing user goal: '{user_goal}'")
        deconstructed_contracts = deconstruct_goal_into_contracts(user_goal)
        print(f"Successfully deconstructed into {len(deconstructed_contracts)} contracts.")

        if not deconstructed_contracts:
            raise ValueError("Agent-Manager failed to generate any contracts for the given goal.")

        # 2. Save the generated contracts to the DynamoDB table
        goal_id = f"goal-{uuid.uuid4()}"
        save_contracts_to_db(deconstructed_contracts, goal_id)
        print(f"Successfully saved contracts to DynamoDB for goal_id: {goal_id}")

        response_body = {
            "goal_id": goal_id,
            "status": "PROCESSING",
            "message": f"{len(deconstructed_contracts)} contracts have been created and are now open on the marketplace."
        }
        
        return {
            "statusCode": 202, # Accepted
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(response_body)
        }

    except (ValueError, TypeError, json.JSONDecodeError) as e:
        return { "statusCode": 400, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": str(e)})}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return { "statusCode": 500, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": "Could not process the goal."})}


def deconstruct_goal_into_contracts(goal_description: str) -> list:
    # ... (код цієї функції залишається БЕЗ ЗМІН) ...
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    prompt = f"""
    You are the Agent-Manager of the KratosNOVA system...
    User Goal: "{goal_description}"
    ...
    Respond with ONLY a valid JSON object containing a single key "contracts"...
    """
    request_body = { "anthropic_version": "bedrock-2023-05-31", "max_tokens": 2048, "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]}
    try:
        response = bedrock_runtime.invoke_model(body=json.dumps(request_body), modelId=model_id, accept="application/json", contentType="application/json")
        response_body = json.loads(response.get("body").read())
        generated_text = response_body.get("content")[0].get("text")
        parsed_response = json.loads(generated_text)
        return parsed_response.get("contracts", [])
    except (ClientError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to deconstruct goal. Details: {e}") from e

def save_contracts_to_db(contracts: list, goal_id: str):
    """
    Adds system fields to contracts and saves them to DynamoDB.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    
    with contracts_table.batch_writer() as batch:
        for contract in contracts:
            # Basic validation for the contract structure from the LLM
            if not all(k in contract for k in ["title", "description", "contract_type"]):
                print(f"Skipping malformed contract from LLM: {contract}")
                continue
            
            item = {
                "contract_id": f"contract-{uuid.uuid4()}",
                "goal_id": goal_id,
                "status": "OPEN",
                "created_at": timestamp,
                "title": contract["title"],
                "description": contract["description"],
                "contract_type": contract["contract_type"]
            }
            batch.put_item(Item=item)