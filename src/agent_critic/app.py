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
SUBMISSIONS_TABLE_NAME = os.environ.get("SUBMISSIONS_TABLE_NAME")
submissions_table = dynamodb.Table(SUBMISSIONS_TABLE_NAME)


def handler(event, context):
    """Main handler for the Critic Agent."""
    _ = context
    print(f"Critic Agent triggered with event: {json.dumps(event)}")

    try:
        contract_id = event.get("contract_id")
        if not contract_id:
            raise ValueError("Input event must include a 'contract_id'.")
        
        # 1. Fetch all submissions for the contract using the GSI
        print(f"Step 1: Fetching submissions for contract_id: {contract_id}")
        submissions = get_submissions_for_contract(contract_id)
        
        if not submissions:
            print("No submissions found for this contract. Exiting.")
            return {"statusCode": 200, "body": "No submissions to process."}
        
        print(f"Found {len(submissions)} submissions.")
        
        # 2. TODO: Fetch the original contract description.
        # 3. TODO: Invoke Bedrock to select a winner.
        # 4. TODO: Update records in DynamoDB.
        
        # For now, just return the fetched submissions for verification.
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Successfully fetched submissions.",
                "submissions": submissions
            })
        }

    except (ValueError, ClientError) as e:
        print(f"Error processing contract evaluation: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def get_submissions_for_contract(contract_id: str) -> list:
    """
    Fetches all submission items for a given contract_id using the GSI.
    """
    try:
        response = submissions_table.query(
            IndexName="contract-id-index",
            KeyConditionExpression=Key('contract_id').eq(contract_id)
        )
        return response.get("Items", [])
    except ClientError as e:
        print(f"Error querying submissions: {e.response['Error']['Message']}")
        raise