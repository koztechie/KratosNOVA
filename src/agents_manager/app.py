import json
import os
import boto3
from datetime import datetime, timezone

# Initialize AWS clients outside the handler for performance
dynamodb = boto3.resource("dynamodb")
AGENTS_TABLE_NAME = os.environ.get("AGENTS_TABLE_NAME")
agents_table = dynamodb.Table(AGENTS_TABLE_NAME)

def handler(event, context):
    """
    Handler for POST /agents endpoint.
    Registers a new agent in the system.
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        # 1. Parse and validate input from the event body
        body = json.loads(event.get("body", "{}"))
        agent_id = body.get("agent_id")
        agent_type = body.get("agent_type")

        if not agent_id or not agent_type:
            raise ValueError("Both 'agent_id' and 'agent_type' are required.")

        if agent_type not in ["ARTIST", "COPYWRITER"]:
            raise ValueError("'agent_type' must be either 'ARTIST' or 'COPYWRITER'.")

        # 2. Prepare the item for DynamoDB
        timestamp = datetime.now(timezone.utc).isoformat()
        
        item = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "reputation": 0,
            "created_at": timestamp,
            "last_active_at": timestamp
        }

        # 3. Write the item to the Agents table
        agents_table.put_item(Item=item)

        # 4. Return a success response
        response_body = {
            "message": "Agent registered successfully",
            "agent": item
        }
        
        return {
            "statusCode": 201, # 201 Created
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response_body)
        }

    except (ValueError, TypeError) as e:
        # Handle validation errors
        return {
            "statusCode": 400, # Bad Request
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }
    except Exception as e:
        # Handle other unexpected errors
        print(f"Error registering agent: {e}")
        return {
            "statusCode": 500, # Internal Server Error
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Could not register the agent."})
        }