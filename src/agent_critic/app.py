"""
Lambda function for the Critic Agent.

This function is triggered by a DynamoDB Stream from the Submissions table.
It evaluates all submissions for a contract, considering agent reputation,
selects a winner using an LLM, and updates the system state in DynamoDB.
"""
import json
import os
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

contracts_table = dynamodb.Table(CONTRACTS_TABLE_NAME)
submissions_table = dynamodb.Table(SUBMISSIONS_TABLE_NAME)
agents_table = dynamodb.Table(AGENTS_TABLE_NAME)
results_table = dynamodb.Table(RESULTS_TABLE_NAME)


def handler(event, context):
    """Main handler for the Critic Agent, triggered by DynamoDB Streams."""
    _ = context
    print(f"Critic triggered by DynamoDB Stream: {json.dumps(event)}")

    for record in event.get("Records", []):
        if record.get("eventName") == "INSERT":
            try:
                new_image = record.get("dynamodb", {}).get("NewImage", {})
                contract_id_obj = new_image.get("contract_id", {})
                contract_id = contract_id_obj.get("S")

                if contract_id:
                    print(f"Processing new submission for contract_id: {contract_id}")
                    process_evaluation(contract_id)
            except Exception as e:
                print(f"Error processing a stream record: {e}")
                print(f"Problematic record: {record}")


def process_evaluation(contract_id: str):
    """
    The core logic for evaluating a contract. Fetches submissions, selects
    a winner, and updates the state of the entire system.
    """
    try:
        contract = get_contract(contract_id)
        if contract.get("status") == "CLOSED":
            print(f"Contract {contract_id} is already closed. No action needed.")
            return

        submissions = get_submissions_for_contract(contract_id)
        if not submissions:
            print(f"No submissions found for contract {contract_id}.")
            return
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
    except (ValueError, ClientError) as e:
        print(f"Error during evaluation for contract {contract_id}: {e}")


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
                    'Keys': [{'agent_id': agent_id} for agent_id in agent_ids]
                }
            }
        )
        agents_data = response.get('Responses', {}).get(AGENTS_TABLE_NAME, [])
        reputation_map = {agent['agent_id']: agent.get('reputation', 0) for agent in agents_data}

        for sub in submissions:
            sub['agent_reputation'] = reputation_map.get(sub.get('agent_id'), 0)
        
        return submissions
    except ClientError as e:
        print(f"Warning: Could not fetch agent reputations. Proceeding without it. Error: {e}")
        for sub in submissions:
            sub['agent_reputation'] = 0
        return submissions


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
    Uses Claude 3 Sonnet to evaluate submissions and select a winner,
    now considering agent reputation as a tie-breaker.
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
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
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
        return json.loads(json_str)
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