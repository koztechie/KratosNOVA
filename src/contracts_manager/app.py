import json

def handler(event, context):
    """
    Handler for GET /contracts endpoint.
    Returns a list of open contracts.
    This is a mock implementation.
    """
    print(f"Received event: {json.dumps(event)}")

    # TODO: Implement actual logic to scan DynamoDB for OPEN contracts

    # Mock response with one open contract
    response_body = {
        "contracts": [
            {
                "contract_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Generate Poster for Sci-Fi Movie",
                "contract_type": "IMAGE",
                "description": "A futuristic movie poster for 'Echoes of Jupiter'...",
                "deadline_at": "2025-09-15T10:05:00Z"
            }
        ]
    }
    
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(response_body)
    }