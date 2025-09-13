"""
Lambda function for the Agent-Manager.
This function handles the POST /goals endpoint, deconstructs the user's goal
into actionable contracts, and puts them on the marketplace.
"""
import json
import os
import boto3
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
        # 1. Parse and validate the user's goal from the request body
        body = json.loads(event.get("body", "{}"))
        user_goal = body.get("description")
        if not user_goal:
            raise ValueError("Request body must include a 'description' for the goal.")

        # 2. Deconstruct the goal into contracts using Bedrock
        print(f"Deconstructing user goal: '{user_goal}'")
        deconstructed_contracts = deconstruct_goal_into_contracts(user_goal)
        print(f"Successfully deconstructed into contracts: {json.dumps(deconstructed_contracts)}")

        # 3. TODO: In the next step, we will write these contracts to DynamoDB.
        # For now, we just return them in the response for verification.

        response_body = {
            "message": "Goal deconstruction successful (dry run).",
            "generated_contracts": deconstructed_contracts
        }
        
        return {
            "statusCode": 200, # Using 200 OK for this test step
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(response_body)
        }

    except (ValueError, TypeError, json.JSONDecodeError) as e:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Could not process the goal."})
        }


def deconstruct_goal_into_contracts(goal_description: str) -> list:
    """
    Uses Claude 3 Sonnet to break down a high-level goal into a list of
    structured contracts for the KratosNOVA marketplace.
    """
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    
    # This is a sophisticated prompt that instructs the model on its role,
    # the available tools (contract types), and the required output format.
    prompt = f"""
    You are the Agent-Manager of the KratosNOVA system, a marketplace for AI agents.
    Your primary function is to deconstruct a high-level user goal into a series of precise,
    machine-readable contracts that specialized agents can execute.

    Available agent specializations (contract_type):
    - "IMAGE": For generating visual content like logos, posters, or illustrations.
    - "TEXT": For generating textual content like slogans, descriptions, or summaries.

    User Goal: "{goal_description}"

    Your task is to analyze the user's goal and create a list of contracts.
    For each contract, you must define a title, a detailed description (which will serve as a prompt
    for the specialist agent), and the appropriate contract_type.

    Respond with ONLY a valid JSON object containing a single key "contracts",
    which is a list of contract objects. Do not include any explanatory text or markdown.
    Example response format:
    {{
      "contracts": [
        {{
          "title": "Create a Visual Logo",
          "description": "A minimalist logo for...",
          "contract_type": "IMAGE"
        }},
        {{
          "title": "Generate Catchy Slogans",
          "description": "Generate 5 slogans for...",
          "contract_type": "TEXT"
        }}
      ]
    }}
    """

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
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
        
        # Parse the JSON string from the model's response
        parsed_response = json.loads(generated_text)
        return parsed_response.get("contracts", [])

    except (ClientError, json.JSONDecodeError) as e:
        print(f"Error communicating with Bedrock or parsing its response: {e}")
        raise ValueError(f"Failed to deconstruct goal. Details: {e}") from e