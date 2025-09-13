"""
Lambda function handler for managing contracts.
Supports:
- GET /contracts: Lists all open contracts.
- GET /contracts/{contract_id}: Gets details for a specific contract.
"""
import json
import os
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
CONTRACTS_TABLE_NAME = os.environ.get("CONTRACTS_TABLE_NAME")
contracts_table = dynamodb.Table(CONTRACTS_TABLE_NAME)


def get_contract(contract_id):
    """Fetches a single contract by its ID."""
    try:
        response = contracts_table.get_item(
            Key={"contract_id": contract_id}
        )
        item = response.get("Item")
        if not item:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"Contract with ID '{contract_id}' not found."})
            }
        return {"statusCode": 200, "body": json.dumps(item)}
    except ClientError as e:
        print(f"Error getting contract: {e.response['Error']['Message']}")
        raise


def list_open_contracts():
    """Scans for and returns all contracts with OPEN status."""
    try:
        response = contracts_table.scan(
            FilterExpression=Attr('status').eq('OPEN')
        )
        items = response.get("Items", [])
        return {"statusCode": 200, "body": json.dumps({"contracts": items})}
    except ClientError as e:
        print(f"Error listing open contracts: {e.response['Error']['Message']}")
        raise


def handler(event, context):
    """Main handler that routes requests based on HTTP method and path."""
    print(f"Received event: {json.dumps(event)}")
    
    http_method = event.get("httpMethod")
    path_parameters = event.get("pathParameters")

    try:
        if http_method == "GET":
            if path_parameters and "contract_id" in path_parameters:
                # This is a GET /contracts/{contract_id} request
                contract_id = path_parameters["contract_id"]
                response = get_contract(contract_id)
            else:
                # This is a GET /contracts request
                response = list_open_contracts()
        else:
            response = {
                "statusCode": 405, # Method Not Allowed
                "body": json.dumps({"error": f"HTTP method {http_method} not supported."})
            }

        # Add common headers to all successful responses
        response["headers"] = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        }
        return response

    except Exception:
        # The specific error is already logged in the helper functions
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "An internal server error occurred."})
        }