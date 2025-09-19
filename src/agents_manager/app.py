"""
Lambda function for managing Agents.

This function can be triggered by two API endpoints:
1.  POST /agents: Registers a new agent in the system.
2.  GET /agents/leaderboard: Returns a list of all agents, sorted by reputation.
"""
import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients outside the handler for performance optimization
dynamodb = boto3.resource("dynamodb")
AGENTS_TABLE_NAME = os.environ.get("AGENTS_TABLE_NAME")
agents_table = dynamodb.Table(AGENTS_TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    """Helper class to convert a DynamoDB item's Decimal types to JSON."""
    def default(self, o):
        if isinstance(o, Decimal):
            if o % 1 > 0:
                return float(o)
            return int(o)
        return super(DecimalEncoder, self).default(o)


def handler(event, context):
    """
    Main handler that routes requests based on HTTP method and path.
    """
    _ = context
    http_method = event.get("httpMethod")
    path = event.get("path", "")

    print(f"Agents Manager triggered for {http_method} {path}")

    try:
        if http_method == "POST" and path.endswith("/agents"):
            return register_agent(event)
        if http_method == "GET" and path.endswith("/leaderboard"):
            return get_leaderboard(event)

        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Not Found"})
        }
    except ClientError as e:
        print(f"An AWS error occurred: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "An internal server error occurred."})
        }


def register_agent(event):
    """
    Handles the logic for the POST /agents endpoint.
    Registers a new agent in the system.
    """
    try:
        body = json.loads(event.get("body", "{}"))
        agent_id = body.get("agent_id")
        agent_type = body.get("agent_type")

        if not agent_id or not agent_type:
            raise ValueError("Both 'agent_id' and 'agent_type' are required.")

        # Allow any type for future extensibility, but validate it's a string
        if not isinstance(agent_type, str):
             raise ValueError("'agent_type' must be a string.")

        timestamp = datetime.now(timezone.utc).isoformat()
        
        item = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "reputation": 0,
            "created_at": timestamp,
            "last_active_at": timestamp
        }

        agents_table.put_item(Item=item)

        response_body = {
            "message": "Agent registered successfully",
            "agent": item
        }
        
        return {
            "statusCode": 201,  # 201 Created
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response_body)
        }

    except (ValueError, TypeError, json.JSONDecodeError) as e:
        return {
            "statusCode": 400,  # Bad Request
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }


def get_leaderboard(event):
    """
    Handles the logic for the GET /agents/leaderboard endpoint.
    Scans the Agents table and returns all agents, sorted by reputation.
    """
    print("Fetching agent leaderboard...")
    response = agents_table.scan()
    agents = response.get("Items", [])
    
    # Handle pagination if the table grows large in the future
    while 'LastEvaluatedKey' in response:
        response = agents_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        agents.extend(response.get("Items", []))

    # Sort agents by reputation in descending order
    sorted_agents = sorted(agents, key=lambda x: x.get('reputation', 0), reverse=True)
    
    print(f"Found {len(sorted_agents)} agents.")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"agents": sorted_agents}, cls=DecimalEncoder)
    }