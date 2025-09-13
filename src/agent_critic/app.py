"""
Lambda function for the Critic Agent.
Evaluates submissions for a completed contract and selects a winner.
"""
import json
import os
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
bedrock_runtime = boto3.client(service_name="bedrock-runtime")

CONTRACTS_TABLE_NAME = os.environ.get("CONTRACTS_TABLE_NAME")
SUBMISSIONS_TABLE_NAME = os.environ.get("SUBMISSIONS_TABLE_NAME")
contracts_table = dynamodb.Table(CONTRACTS_TABLE_NAME)
submissions_table = dynamodb.Table(SUBMISSIONS_TABLE_NAME)


def handler(event, context):
    """Main handler for the Critic Agent."""
    _ = context
    print(f"Critic Agent triggered with event: {json.dumps(event)}")

    try:
        contract_id = event.get("contract_id")
        if not contract_id:
            raise ValueError("Input event must include a 'contract_id'.")
        
        # 1. Fetch all submissions for the contract
        print(f"Step 1: Fetching submissions for contract_id: {contract_id}")
        submissions = get_submissions_for_contract(contract_id)
        if not submissions:
            print("No submissions found for this contract. Exiting.")
            return {"statusCode": 200, "body": json.dumps({"message": "No submissions to process."})}
        print(f"Found {len(submissions)} submissions.")

        # 2. Fetch the original contract
        print("Step 2: Fetching original contract details.")
        contract = get_contract(contract_id)

        # 3. Invoke Bedrock to select a winner
        print("Step 3: Invoking Bedrock to select a winner.")
        winning_submission = select_winner(contract, submissions)
        print(f"Bedrock selected winner: {json.dumps(winning_submission)}")

        # 4. TODO: Update records in DynamoDB.
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Successfully selected a winner.",
                "winning_submission": winning_submission
            })
        }

    except (ValueError, ClientError) as e:
        print(f"Error processing contract evaluation: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def get_submissions_for_contract(contract_id: str) -> list:
    # ... (код цієї функції залишається БЕЗ ЗМІН) ...
    try:
        response = submissions_table.query(IndexName="contract-id-index", KeyConditionExpression=Key('contract_id').eq(contract_id))
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
    """
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    
    # Prepare the submissions in a readable format for the model
    submissions_text = ""
    for sub in submissions:
        submissions_text += f"<submission>\n"
        submissions_text += f"  <id>{sub['submission_id']}</id>\n"
        submissions_text += f"  <content>{sub['submission_data']}</content>\n"
        submissions_text += f"</submission>\n"

    prompt = f"""
    You are an expert Art Director and Chief Editor responsible for judging submissions in a creative competition.
    Your task is to select the single best submission that most effectively and creatively fulfills the original creative brief.

    **Creative Brief (The Original Task):**
    <brief>
    <title>{contract['title']}</title>
    <description>{contract['description']}</description>
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
        response = bedrock_runtime.invoke_model(
            body=json.dumps(request_body), modelId=model_id
        )
        response_body = json.loads(response.get("body").read())
        generated_text = response_body.get("content")[0].get("text")
        
        # Find and parse the JSON object from the model's response
        json_start_index = generated_text.find('{')
        if json_start_index == -1:
            raise ValueError("No JSON object found in the model's response.")
        json_str = generated_text[json_start_index:]
        
        return json.loads(json_str)

    except (ClientError, json.JSONDecodeError, ValueError) as e:
        print(f"Error selecting winner via Bedrock: {e}")
        raise ValueError(f"Failed to select a winner. Details: {e}") from e