"""
Lambda function handler for listing open contracts.
"""
import json
import os
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

# Initialize AWS clients outside the handler for performance
dynamodb = boto3.resource("dynamodb")
CONTRACTS_TABLE_NAME = os.environ.get("CONTRACTS_TABLE_NAME")
contracts_table = dynamodb.Table(CONTRACTS_TABLE_NAME)


def handler(event, context):
    """
    Handler for GET /contracts endpoint.

    Scans the Contracts table and returns a list of all contracts with OPEN status.
    """
    print(f"Received event: {json.dumps(event)}")
    # The 'context' argument is unused in this simple function, which is acceptable.

    try:
        # A scan can be inefficient on large tables, but for the scale of this
        # hackathon (a few hundred contracts at most), it is perfectly acceptable.
        # A more optimized solution would use a Global Secondary Index on 'status'.
        response = contracts_table.scan(
            FilterExpression=Attr('status').eq('OPEN')
        )

        items = response.get("Items", [])

        response_body = {
            "contracts": items
        }

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response_body)
        }

    except ClientError as e:
        # Handle specific Boto3 errors
        print(f"Error listing open contracts: {e.response['Error']['Message']}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Could not retrieve the list of contracts."})
        }