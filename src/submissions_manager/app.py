"""
Lambda function handler for submitting work to a contract.
"""
import json
import os
import boto3
import uuid
from datetime import datetime, timezone
from botocore.exceptions import ClientError

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
CONTRACTS_TABLE_NAME = os.environ.get("CONTRACTS_TABLE_NAME")
SUBMISSIONS_TABLE_NAME = os.environ.get("SUBMISSIONS_TABLE_NAME")
contracts_table = dynamodb.Table(CONTRACTS_TABLE_NAME)
submissions_table = dynamodb.Table(SUBMISSIONS_TABLE_NAME)

def handler(event, context):
    """
    Handler for POST /contracts/{contract_id}/submissions endpoint.
    Validates the contract and creates a new submission item.
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        # 1. Get contract_id from the path
        path_parameters = event.get("pathParameters", {})
        contract_id = path_parameters.get("contract_id")
        if not contract_id:
            raise ValueError("'contract_id' is required in the path.")

        # 2. Parse and validate input from the event body
        body = json.loads(event.get("body", "{}"))
        agent_id = body.get("agent_id")
        submission_data = body.get("submission_data")

        if not agent_id or not submission_data:
            raise ValueError("Both 'agent_id' and 'submission_data' are required in the body.")

        # 3. Check if the contract exists and is OPEN
        try:
            contract_response = contracts_table.get_item(Key={"contract_id": contract_id})
            contract = contract_response.get("Item")

            if not contract:
                return {
                    "statusCode": 404,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": f"Contract with ID '{contract_id}' not found."})
                }
            
            if contract.get("status") != "OPEN":
                return {
                    "statusCode": 403, # Forbidden
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": f"Contract with ID '{contract_id}' is closed and does not accept submissions."})
                }
        except ClientError as e:
            print(f"Error fetching contract: {e.response['Error']['Message']}")
            raise # Re-raise to be caught by the general error handler

        # 4. Prepare and write the submission item
        submission_id = f"sub-{uuid.uuid4()}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        item = {
            "submission_id": submission_id,
            "contract_id": contract_id,
            "agent_id": agent_id,
            "submission_data": submission_data,
            "created_at": timestamp,
            "is_winner": False
        }
        
        submissions_table.put_item(Item=item)

        # 5. Return a success response
        response_body = {
            "submission_id": submission_id,
            "message": "Submission received successfully."
        }
        
        return {
            "statusCode": 201, # Created
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(response_body)
        }

    except (ValueError, TypeError) as e:
        return {
            "statusCode": 400, # Bad Request
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Could not process the submission."})
        }