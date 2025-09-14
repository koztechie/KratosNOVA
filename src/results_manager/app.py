"""
Lambda function for the Results Manager.

This function handles the GET /goals/{goal_id} endpoint, fetching the final,
winning results for a user's goal from the Results table.
"""
import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from decimal import Decimal

# Helper to handle Decimal types in JSON serialization
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
RESULTS_TABLE_NAME = os.environ.get("RESULTS_TABLE_NAME")
results_table = dynamodb.Table(RESULTS_TABLE_NAME)


def handler(event, context):
    """
    Handler for GET /goals/{goal_id} endpoint.
    Queries the Results table for all items matching the goal_id.
    """
    _ = context
    print(f"Results Manager triggered with event: {json.dumps(event)}")

    try:
        path_parameters = event.get("pathParameters", {})
        goal_id = path_parameters.get("goal_id")
        if not goal_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "'goal_id' is required in the path."})
            }

        print(f"Fetching results for goal_id: {goal_id}")
        
        # Query the Results table using the goal_id partition key
        response = results_table.query(
            KeyConditionExpression=Key('goal_id').eq(goal_id)
        )
        items = response.get("Items", [])
        
        status = "COMPLETED" if items else "PROCESSING"
        print(f"Found {len(items)} results. Status is '{status}'.")

        response_body = {
            "goal_id": goal_id,
            "status": status,
            "results": items
        }

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response_body, cls=DecimalEncoder)
        }

    except ClientError as e:
        print(f"Error fetching results from DynamoDB: {e.response['Error']['Message']}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Could not retrieve results."})
        }
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "An internal server error occurred."})
        }