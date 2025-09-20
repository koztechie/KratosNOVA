"""
Lambda function handler for managing contracts.

This function acts as a router for two primary operations:
- GET /contracts: Lists all contracts currently in an 'OPEN' state.
- GET /contracts/{contract_id}: Gets the detailed information for a single, specific contract.
"""
import json
import os
import traceback
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr, Key

# Helper class to convert DynamoDB's Decimal types into standard JSON numbers.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            # Check if it's a float or an int
            if o % 1 > 0:
                return float(o)
            return int(o)
        return super(DecimalEncoder, self).default(o)

# Initialize AWS clients and DynamoDB table resource outside the handler for performance.
dynamodb = boto3.resource("dynamodb")
CONTRACTS_TABLE_NAME = os.environ.get("CONTRACTS_TABLE_NAME")
contracts_table = dynamodb.Table(CONTRACTS_TABLE_NAME)


def get_contract(contract_id: str) -> dict:
    """
    Fetches a single contract by its ID using a direct GetItem call.
    """
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
        return {
            "statusCode": 200,
            "body": json.dumps(item, cls=DecimalEncoder)
        }
    except ClientError as e:
        print(f"Error getting contract details: {e.response['Error']['Message']}")
        raise


def list_open_contracts() -> dict:
    """
    Scans the entire Contracts table and returns all items with the status 'OPEN'.
    Note: A scan is acceptable for the MVP scale of this hackathon. For a production
    system with many contracts, a Global Secondary Index (GSI) on the 'status'
    attribute would be a more performant solution.
    """
    try:
        response = contracts_table.scan(
            FilterExpression=Attr('status').eq('OPEN')
        )
        items = response.get("Items", [])
        return {
            "statusCode": 200,
            "body": json.dumps({"contracts": items}, cls=DecimalEncoder)
        }
    except ClientError as e:
        print(f"Error listing open contracts (ClientError): {e.response['Error']['Message']}")
        raise


def handler(event, context):
    """
    Main handler that routes incoming API Gateway requests based on the
    HTTP method and path parameters.
    """
    _ = context
    print(f"Contracts Manager received event: {json.dumps(event)}")
    
    http_method = event.get("httpMethod")
    path_parameters = event.get("pathParameters")

    try:
        if http_method == "GET":
            # Route to get a single contract if an ID is in the path
            if path_parameters and "contract_id" in path_parameters:
                response = get_contract(path_parameters["contract_id"])
            # Otherwise, route to get the list of all open contracts
            else:
                response = list_open_contracts()
        else:
            response = {
                "statusCode": 405, # Method Not Allowed
                "body": json.dumps({"error": f"HTTP method {http_method} is not supported."})
            }

        # Add common CORS headers to all successful responses
        if "headers" not in response:
            response["headers"] = {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        return response

    except Exception as e:
        # Catch-all for any unhandled exceptions in the helper functions
        print(f"FATAL: An unhandled exception occurred in the handler: {e}")
        traceback.print_exc()
        
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "An internal server error occurred."})
        }