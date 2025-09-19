"""
Lambda function for the Critic Agent.

This function can be triggered by two sources:
1.  A DynamoDB Stream from the Submissions table (automated evaluation).
2.  A direct API Gateway call (manual evaluation for failed contracts).

It evaluates submissions, selects a winner, and can reformulate contracts
that received no submissions. It uses a DynamoDB-based cache to avoid
redundant, expensive calls to the Bedrock API.
"""
import json
import os
import uuid
import time
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
bedrock_runtime = boto3.client(service_name="bedrock-runtime")

# Get table names from environment variables
CONTRACTS_TABLE_NAME = os.environ.get("CONTRACTS_TABLE_NAME")
SUBMISSIONS_TABLE_NAME = os.environ.get("SUBMISSIONS_TABLE_NAME")
AGENTS_TABLE_NAME = os.environ.get("AGENTS_TABLE_NAME")
RESULTS_TABLE_NAME = os.environ.get("RESULTS_TABLE_NAME")
BEDROCK_CACHE_TABLE_NAME = os.environ.get("BEDROCK_CACHE_TABLE_NAME")

contracts_table = dynamodb.Table(CONTRACTS_TABLE_NAME)
submissions_table = dynamodb.Table(SUBMISSIONS_TABLE_NAME)
agents_table = dynamodb.Table(AGENTS_TABLE_NAME)
results_table = dynamodb.Table(RESULTS_TABLE_NAME)
bedrock_cache_table = dynamodb.Table(BEDROCK_CACHE_TABLE_NAME)


def handler(event, context):
    """
    Main handler that routes requests based on the trigger source.
    """
    _ = context
    print(f"Critic Agent triggered with event: {json.dumps(event)}")

    # Route based on trigger source
    if "Records" in event:  # Triggered by DynamoDB Stream
        for record in event.get("Records", []):
            if record.get("eventName") == "INSERT":
                try:
                    new_image = record.get("dynamodb", {}).get("NewImage", {})
                    contract_id_obj = new_image.get("contract_id", {})
                    contract_id = contract_id_obj.get("S")
                    if contract_id:
                        print(f"Processing new submission for contract_id: {contract_id}")
                        process_evaluation(contract_id)
                except (ValueError, ClientError) as e:
                    print(f"Error processing a stream record: {e}")
                    print(f"Problematic record: {record}")
        return {"statusCode": 200, "body": "Stream event processed."}

    if "httpMethod" in event:  # Triggered by API Gateway
        if event["httpMethod"] == "POST":
            path_params = event.get("pathParameters", {})
            contract_id = path_params.get("contract_id")
            if contract_id:
                print(f"Manual evaluation triggered for contract: {contract_id}")
                return process_evaluation(contract_id)

    return {
        "statusCode": 400,
        "body": json.dumps({"error": "Unknown trigger or invalid request."})
    }


def process_evaluation(contract_id: str) -> dict:
    """
    The core logic for evaluating a contract. Fetches submissions, selects a
    winner, or reformulates the contract if no submissions are found.
    Returns a dict suitable for an API Gateway response.
    """
    try:
        contract = get_contract(contract_id)
        if contract.get("status") != "OPEN":
            message = (f"Contract {contract_id} is not OPEN "
                       f"(current status: {contract.get('status')}). No action taken.")
            print(message)
            return {"statusCode": 200, "body": json.dumps({"message": message})}

        submissions = get_submissions_for_contract(contract_id)

        if not submissions:
            print(f"No submissions found for contract {contract_id}. Initiating reformulation.")
            new_contract = reformulate_and_repost_contract(contract)
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({
                    "message": "Contract had no submissions and was reformulated.",
                    "original_contract_id": contract_id,
                    "new_contract": new_contract
                })
            }

        print(f"Found {len(submissions)} submissions for evaluation.")
        enriched_submissions = enrich_submissions_with_reputation(submissions)
        winning_result = select_winner(contract, enriched_submissions)
        winning_submission_id = winning_result.get("winning_submission_id")

        if not winning_submission_id:
            raise ValueError("Critic model failed to return a winning_submission_id.")
        print(f"Bedrock selected winner: {winning_submission_id}")

        winner_submission_item = next(
            (sub for sub in enriched_submissions if sub.get('submission_id') == winning_submission_id),
            None
        )
        if winner_submission_item:
            winning_agent_id = winner_submission_item.get("agent_id")
            update_winner_submission(winning_submission_id)
            if winning_agent_id:
                update_agent_reputation(winning_agent_id, 1)
            save_final_result(contract.get("goal_id"), contract, winner_submission_item)

        update_contract_status(contract_id, "CLOSED")
        print(f"Successfully processed and closed contract {contract_id}.")

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({
                "message": "Successfully selected a winner and updated system state.",
                "winning_submission_id": winning_submission_id
            })
        }

    except (ValueError, ClientError) as e:
        print(f"Error during evaluation for contract {contract_id}: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def enrich_submissions_with_reputation(submissions: list) -> list:
    """
    Fetches the reputation for each agent who made a submission using an
    efficient batch_get_item call.
    """
    agent_ids = {sub.get("agent_id") for sub in submissions if sub.get("agent_id")}
    if not agent_ids:
        return submissions

    try:
        response = dynamodb.batch_get_item(
            RequestItems={
                AGENTS_TABLE_NAME: {
                    'Keys': [{'agent_id': agent_id} for agent_id in list(agent_ids)]
                }
            }
        )
        agents_data = response.get('Responses', {}).get(AGENTS_TABLE_NAME, [])
        reputation_map = {
            agent['agent_id']: agent.get('reputation', 0) for agent in agents_data
        }

        for sub in submissions:
            sub['agent_reputation'] = reputation_map.get(sub.get('agent_id'), 0)
        
        return submissions
    except ClientError as e:
        print(f"Warning: Could not fetch agent reputations. Proceeding without it. Error: {e}")
        for sub in submissions:
            sub['agent_reputation'] = 0
        return submissions


def reformulate_and_repost_contract(original_contract: dict) -> dict:
    """
    Takes a failed contract, uses an LLM to improve its description,
    and creates a new contract on the marketplace. This operation is cached.
    """
    contract_id = original_contract.get("contract_id")
    print(f"Reformulating contract: {contract_id}")
    
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    old_description = original_contract.get("description", "")
    
    prompt = f"""
    You are a Creative Director tasked with improving a task description that failed to attract any submissions from AI agents.
    The original description was:
    <original_description>
    {old_description}
    </original_description>

    Your job is to rewrite this description to be clearer, more engaging, and more appealing to a creative AI agent.
    Focus on providing more context, better examples, or a more inspiring tone.
    Respond with ONLY the new description text, without any preamble.
    """
    
    # --- Caching Logic ---
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    try:
        cache_response = bedrock_cache_table.get_item(Key={'prompt_hash': prompt_hash})
        if 'Item' in cache_response:
            print("CACHE HIT! Returning stored reformulation.")
            new_description = cache_response['Item']['response']
        else:
            print("CACHE MISS. Calling Bedrock for reformulation...")
            request_body = {
                "anthropic_version": "bedrock-2023-05-31", "max_tokens": 2048,
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            }
            response = bedrock_runtime.invoke_model(body=json.dumps(request_body), modelId=model_id)
            response_body = json.loads(response.get("body").read())
            new_description = response_body.get("content")[0].get("text")
            
            ttl = int(time.time()) + (24 * 60 * 60)
            bedrock_cache_table.put_item(
                Item={'prompt_hash': prompt_hash, 'response': new_description, 'ttl': ttl}
            )
    except (ClientError, json.JSONDecodeError, ValueError) as e:
        print(f"Cache or Bedrock error during reformulation: {e}. Using original description.")
        new_description = old_description + " (reformulation failed, please try again)"
    
    update_contract_status(contract_id, "FAILED_REPOSTED")

    timestamp = datetime.now(timezone.utc).isoformat()
    new_contract_item = {
        "contract_id": f"contract-{uuid.uuid4()}",
        "goal_id": original_contract.get("goal_id"),
        "status": "OPEN",
        "created_at": timestamp,
        "title": original_contract.get("title") + " (V2)",
        "description": new_description,
        "contract_type": original_contract.get("contract_type"),
        "budget": original_contract.get("budget", Decimal('0'))
    }
    
    contracts_table.put_item(Item=new_contract_item)
    print(f"Successfully created new contract: {new_contract_item['contract_id']}")
    return new_contract_item


def get_submissions_for_contract(contract_id: str) -> list:
    """Fetches all submission items for a given contract_id using the GSI."""
    try:
        response = submissions_table.query(
            IndexName="contract-id-index",
            KeyConditionExpression=Key('contract_id').eq(contract_id)
        )
        return response.get("Items", [])
    except ClientError as e:
        print(f"Error querying submissions: {e.response['Error']['Message']}")
        raise


def get_contract(contract_id: str) -> dict:
    """Fetches a single contract by its ID."""
    try:
        response = contracts_table.get_item(Key={"contract_id": contract_id})
        item = response.get("Item")
        if not item:
            raise ValueError(f"Contract with ID '{contract_id}' not found.")
        return item
    except ClientError as e:
        print(f"Error getting contract: {e.response['Error']['Message']}")
        raise


def select_winner(contract: dict, submissions: list) -> dict:
    """
    Uses Claude 3 Sonnet to evaluate submissions and select a winner.
    This operation is cached to prevent re-evaluation of the same set of submissions.
    """
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    submissions_text = ""
    for sub in submissions:
        submissions_text += (
            f"<submission>\n"
            f"  <id>{sub.get('submission_id')}</id>\n"
            f"  <content>{sub.get('submission_data')}</content>\n"
            f"  <author_reputation>{sub.get('agent_reputation', 0)}</author_reputation>\n"
            f"</submission>\n"
        )
    prompt = f"""
    You are an expert Art Director and Chief Editor responsible for judging submissions in a creative competition.
    Your task is to select the single best submission that most effectively and creatively fulfills the original creative brief.

    **Creative Brief (The Original Task):**
    <brief>
    <title>{contract.get('title', 'N/A')}</title>
    <description>{contract.get('description', 'N/A')}</description>
    </brief>

    **Submissions to Evaluate:**
    Each submission includes the content and the reputation score of the agent who created it.
    <submissions>
    {submissions_text}
    </submissions>

    **Your Instructions:**
    1.  Carefully review the Creative Brief.
    2.  Evaluate each submission primarily on its relevance, creativity, and quality.
    3.  If two or more submissions are of very similar high quality, give a slight preference to the submission from the agent with a higher `author_reputation` score.
    4.  Choose the ONE submission that represents the absolute best final choice.
    5.  Provide a brief, constructive justification for your choice.

    Respond with ONLY a single, raw JSON object in the following format. Do not include any text before or after the JSON object.
    {{
      "winning_submission_id": "<The ID of the winning submission>",
      "justification": "<Your brief reason for choosing the winner>"
    }}
    """

    # --- Caching Logic ---
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    try:
        cache_response = bedrock_cache_table.get_item(Key={'prompt_hash': prompt_hash})
        if 'Item' in cache_response:
            print("CACHE HIT! Returning stored winner selection.")
            return json.loads(cache_response['Item']['response'])
    except ClientError as e:
        print(f"Cache read error: {e}")

    print("CACHE MISS. Calling Bedrock for winner selection...")
    request_body = {
        "anthropic_version": "bedrock-2023-05-31", "max_tokens": 2048,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    }
    try:
        response = bedrock_runtime.invoke_model(body=json.dumps(request_body), modelId=model_id)
        response_body = json.loads(response.get("body").read())
        generated_text = response_body.get("content")[0].get("text")
        
        json_start_index = generated_text.find('{')
        if json_start_index == -1:
            raise ValueError("No JSON object found in the model's response.")
        json_str = generated_text[json_start_index:]
        result = json.loads(json_str)

        # Save the new result to cache
        ttl = int(time.time()) + (24 * 60 * 60)  # 24 hour TTL
        bedrock_cache_table.put_item(
            Item={
                'prompt_hash': prompt_hash,
                'response': json.dumps(result),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'ttl': ttl
            }
        )
        return result
    except (ClientError, json.JSONDecodeError, ValueError) as e:
        print(f"Error selecting winner via Bedrock: {e}")
        raise ValueError(f"Failed to select a winner. Details: {e}") from e


def update_winner_submission(submission_id: str):
    """Updates the submission item to mark it as the winner."""
    try:
        print(f"Marking submission {submission_id} as winner...")
        submissions_table.update_item(
            Key={"submission_id": submission_id},
            UpdateExpression="SET is_winner = :val",
            ExpressionAttributeValues={":val": True}
        )
    except ClientError as e:
        print(f"Error updating submission winner status: {e.response['Error']['Message']}")
        raise


def update_contract_status(contract_id: str, status: str):
    """Updates the status of a contract."""
    try:
        print(f"Updating contract {contract_id} status to {status}...")
        contracts_table.update_item(
            Key={"contract_id": contract_id},
            UpdateExpression="SET #s = :val",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":val": status}
        )
    except ClientError as e:
        print(f"Error updating contract status: {e.response['Error']['Message']}")
        raise


def update_agent_reputation(agent_id: str, score: int):
    """Atomically increases the reputation score of an agent."""
    try:
        print(f"Updating reputation for agent {agent_id} by {score}...")
        agents_table.update_item(
            Key={"agent_id": agent_id},
            UpdateExpression="ADD reputation :inc",
            ExpressionAttributeValues={":inc": Decimal(score)},
            ReturnValues="UPDATED_NEW"
        )
    except ClientError as e:
        print(f"Warning: Could not update reputation for agent {agent_id}. "
              f"Error: {e.response['Error']['Message']}")


def save_final_result(goal_id: str, contract: dict, winner: dict):
    """Saves the winning submission to the final Results table."""
    if not goal_id:
        print("Warning: Cannot save final result because goal_id is missing from the contract.")
        return
        
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        item = {
            "goal_id": goal_id,
            "contract_id": contract.get("contract_id"),
            "winning_submission_id": winner.get("submission_id"),
            "winning_agent_id": winner.get("agent_id"),
            "submission_data": winner.get("submission_data"),
            "contract_type": contract.get("contract_type"),
            "evaluated_at": timestamp
        }
        print(f"Saving final result: {item}")
        results_table.put_item(Item=item)
    except ClientError as e:
        print(f"Warning: Could not save final result. Error: {e.response['Error']['Message']}")