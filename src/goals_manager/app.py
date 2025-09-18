"""
Lambda function for the Agent-Manager.

This function handles the POST /goals endpoint. It uses a Large Language Model
with Chain-of-Thought prompting to deconstruct a high-level user goal into a
series of actionable, structured contracts, and then persists these contracts
to the DynamoDB table.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal  # <-- ВИПРАВЛЕНО: Додано відсутній імпорт

import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients outside the handler for performance optimization
dynamodb = boto3.resource("dynamodb")
bedrock_runtime = boto3.client(service_name="bedrock-runtime")

# Get config from environment variables set by CDK
CONTRACTS_TABLE_NAME = os.environ.get("CONTRACTS_TABLE_NAME")
contracts_table = dynamodb.Table(CONTRACTS_TABLE_NAME)


def handler(event, context):
    """
    Main handler for the Agent-Manager. It orchestrates the process of
    deconstructing a goal and creating contracts.
    """
    _ = context  # Acknowledge unused context argument
    print(f"Agent-Manager triggered with event: {json.dumps(event)}")

    try:
        body = json.loads(event.get("body", "{}"))
        user_goal = body.get("description")
        if not user_goal:
            raise ValueError("Request body must include a 'description' for the goal.")

        # Step 1: Deconstruct the goal into contracts using Bedrock
        print(f"Deconstructing user goal: '{user_goal}'")
        deconstructed_contracts = deconstruct_goal_into_contracts(user_goal)
        print(f"Successfully deconstructed into {len(deconstructed_contracts)} contracts.")

        if not deconstructed_contracts:
            raise ValueError("Agent-Manager failed to generate any contracts for the given goal.")

        # Step 2: Save the generated contracts to the DynamoDB table
        goal_id = f"goal-{uuid.uuid4()}"
        save_contracts_to_db(deconstructed_contracts, goal_id)
        print(f"Successfully saved contracts to DynamoDB for goal_id: {goal_id}")

        response_body = {
            "goal_id": goal_id,
            "status": "PROCESSING",
            "message": (f"{len(deconstructed_contracts)} contracts have been created "
                        "and are now open on the marketplace.")
        }

        return {
            "statusCode": 202,  # Accepted
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response_body)
        }

    except (ValueError, TypeError, json.JSONDecodeError) as e:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }
    except ClientError as e:
        print(f"An unexpected AWS error occurred: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Could not process the goal due to an internal error."})
        }


def deconstruct_goal_into_contracts(goal_description: str) -> list:
    """
    Uses Claude 3 Sonnet with Chain-of-Thought prompting to break down a
    high-level goal into a list of structured contracts.
    """
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

    prompt = f"""
    You are the Agent-Manager of the KratosNOVA system, a highly-structured marketplace for AI agents.
    Your primary function is to deconstruct a high-level user goal into a series of precise, machine-readable contracts and allocate a budget for each.

    **Follow this process:**
    1.  **Think step-by-step**: Inside a <scratchpad> block, analyze the user's goal. Break it down into fundamental needs. Identify the distinct creative assets required. For each asset, determine the most appropriate `contract_type`. Formulate a clear and detailed prompt (description) for the specialist agent. Finally, decide on a fair budget allocation for each task from a total pool of 100 credits, considering its complexity.
    2.  **Format the output**: After your analysis in the scratchpad, generate a single, raw JSON object. This object must contain one key: "contracts", whose value is a list of the contract objects you designed.

    **Total available budget for this goal is 100 credits.**

    **Available agent specializations (contract_type) and their relative complexity:**
    - "IMAGE": A complex and valuable task (should receive a significant portion of the budget).
    - "RESEARCH": An important, foundational task (should receive a medium to high portion of the budget).
    - "TEXT": A standard, less complex task (should receive a smaller portion of the budget).

    **User Goal:** "{goal_description}"

    **Your task is to analyze the user's goal and create a list of contracts. Each contract object must contain:**
    1.  `title`: A short, descriptive title for the task.
    2.  `description`: A detailed prompt for the specialist agent who will perform the task.
    3.  `contract_type`: Must be one of "IMAGE", "TEXT", or "RESEARCH".
    4.  `budget`: A number (integer) representing the portion of the 100 credits you allocate to this task. The sum of all budgets should logically not exceed 100.

    **Your Response:**
    Your final output MUST contain ONLY the raw JSON object. Do not include the <scratchpad> block or any other text outside of the final JSON structure.
    """

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
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

        print(f"Raw model response including scratchpad (if any):\n---\n{generated_text}\n---")

        json_start_index = generated_text.find('{')
        if json_start_index == -1:
            raise ValueError("No JSON object found in the model's response.")

        json_str = generated_text[json_start_index:]
        parsed_response = json.loads(json_str)

        if "contracts" not in parsed_response or not isinstance(parsed_response["contracts"], list):
            raise ValueError("The 'contracts' key (a list) is missing in the parsed JSON.")

        return parsed_response["contracts"]

    except (ClientError, json.JSONDecodeError, ValueError) as e:
        print(f"Error communicating with Bedrock or parsing its response: {e}")
        raise ValueError(f"Failed to deconstruct goal. Details: {e}") from e


def save_contracts_to_db(contracts: list, goal_id: str):
    """
    Adds system fields to contracts and saves them to DynamoDB using a batch writer
    for efficiency.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    with contracts_table.batch_writer() as batch:
        for contract in contracts:
            if not all(k in contract for k in ["title", "description", "contract_type", "budget"]):
                print(f"Skipping malformed contract from LLM: {contract}")
                continue

            item = {
                "contract_id": f"contract-{uuid.uuid4()}",
                "goal_id": goal_id,
                "status": "OPEN",
                "created_at": timestamp,
                "title": contract["title"],
                "description": contract["description"],
                "contract_type": contract["contract_type"],
                "budget": Decimal(str(contract.get("budget", 0)))
            }
            batch.put_item(Item=item)