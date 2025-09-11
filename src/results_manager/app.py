import json

def handler(event, context):
    """
    A simple handler function that returns a greeting.
    """
    print("Handler was called")
    
    response_body = {
        "message": "Hello, KratosNOVA!"
    }
    
    response = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*" # Required for CORS
        },
        "body": json.dumps(response_body)
    }
    
    return response