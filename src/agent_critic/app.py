"""
Lambda function for the Critic Agent.

This function is responsible for evaluating submissions for a completed
contract, selecting a winner using an LLM, and updating the system state
in DynamoDB, including agent reputation.
"""
import json
import os
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

# Initialize AWS clients outside the handler for performance optimization
dynamodb = boto3.resource("dynamodb")
bedrock_runtime = boto3.client(service_name="bedrock-runtime")

# Get table names from environment variables set by CDK
CONTRACTS_TABLE_NAME = os.environ.get("CONTRACTS_TABLE_NAME")
SUBMISSIONS_TABLE_NAME = os.environ.get("SUBMISSIONS_TABLE_NAME")
AGENTS_TABLE_NAME = os.environ.get("AGENTS_TABLE_NAME")
contracts_table = dynamodb.Table(CONTRACTS_TABLE_NAME)
submissions_table = dynamodb.Table(SUBMISSIONS_TABLE_NAME)
agents_table = dynamodb.Table(AGENTS_TABLE_NAME)


def handler(event, context):
    """
    Main handler for the Critic Agent. Orchestrates the evaluation process.
    """
    _ = context  # Acknowledge unused context argument
    print(f"Critic Agent triggered with event: {json.dumps(event)}")

    try:
        contract_id = event.get("contract_id")
        if not contract_id:
            raise ValueError("Input event must include a 'contract_id'.")

        # Step 1: Fetch all submissions for the contract
        submissions = get_submissions_for_contract(contract_id)
        if not submissions:
            print(f"No submissions found for contract {contract_id}. Marking as closed.")
            update_contract_status(contract_id, "CLOSED")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No submissions to process. Contract closed."})
            }
        print(f"Found {len(submissions)} submissions for contract {contract_id}.")

        # Step 2: Fetch the original contract for its description
        contract = get_contract(contract_id)

        # Step 3: Invoke Bedrock to select a winner
        winning_result = select_winner(contract, submissions)
        winning_submission_id = winning_result.get("winning_submission_id")
        if not winning_submission_id:
            raise ValueError("Critic model failed to return a winning_submission_id.")
        print(f"Bedrock selected winner: {winning_submission_id}")

        # Step 4: Update the system state in DynamoDB
        print("Step 4: Updating records in DynamoDB.")
        
        # Find the full submission item to get the winner's agent_id
        winner_submission_item = next(
            (sub for sub in submissions if sub.get('submission_id') == winning_submission_id),
            None
        )
        
        if winner_submission_item:
            winning_agent_id = winner_submission_item.get("agent_id")
            update_winner_submission(winning_submission_id)
            if winning_agent_id:
                update_agent_reputation(winning_agent_id, 1)
        else:
            print(f"Warning: Winning submission ID {winning_submission_id} not found "
                  "in the fetched list. Cannot update reputation.")
        
        update_contract_status(contract_id, "CLOSED")
        print("Successfully updated DynamoDB records.")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Successfully selected a winner and updated system state.",
                "winning_submission_id": winning_submission_id
            })
        }

    except (ValueError, ClientError) as e:
        print(f"Error processing contract evaluation: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


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
    """Uses Claude 3 Sonnet to evaluate submissions and select a winner."""
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    submissions_text = ""
    for sub in submissions:
        submissions_text += (
            f"<submission>\n"
            f"  <id>{sub.get('submission_id')}</id>\n"
            f"  <content>{sub.get('submission_data')}</content>\n"
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
    <submissions>
    {submissions_text}
    </submissions>

    **Your Instructions:**
    1.  Carefully review the Creative Brief.
    2.  Evaluate each submission based on its relevance, creativity, and quality.
    3.  Choose the ONE submission that is the absolute best fit for the brief.
    4.  Provide a brief, constructive justification for your choice.

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
        # It's better not to fail the whole process if reputation update fails.
        # We just log a warning.
        print(f"Warning: Could not update reputation for agent {agent_id}. "
              f"Error: {e.response['Error']['Message']}")