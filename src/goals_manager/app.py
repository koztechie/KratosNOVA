"""
Lambda function for the Agent-Manager (Conversational).

This function acts as the brain of the conversation. It handles the initial
POST /goals request, analyzes the user's prompt for completeness, and either
starts a clarifying dialogue or sends the completed goal for processing.
It also handles subsequent messages in an ongoing conversation.
"""
import json
import os
import uuid
import boto3
from botocore.exceptions import ClientError

# Initialize clients
sqs = boto3.client("sqs")
bedrock_runtime = boto3.client(service_name="bedrock-runtime")

# Get config from environment variables
QUEUE_URL = os.environ.get("GOAL_DECONSTRUCTION_QUEUE_URL")


def handler(event, context):
    """
    Main handler that routes requests based on whether it's a new goal
    or part of an ongoing conversation.
    """
    _ = context
    path = event.get("path", "")
    print(f"Goals Manager triggered for path: {path}")

    try:
        if path.startswith("/goals/conversation/"):
            return continue_conversation(event)
        
        return start_new_conversation(event)

    except (ValueError, TypeError, json.JSONDecodeError) as e:
        print(f"Input Error: {e}")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }
    except ClientError as e:
        print(f"AWS API Error: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "An internal service error occurred."})
        }


def start_new_conversation(event):
    """
    Handles the initial POST /goals request. Analyzes the prompt and decides
    whether to start a conversation or process the goal immediately.
    """
    body = json.loads(event.get("body", "{}"))
    initial_prompt = body.get("description", "").strip()

    if not initial_prompt:
        raise ValueError("Request body must include a non-empty 'description'.")

    # Use an LLM to analyze if the prompt is detailed enough
    analysis = analyze_initial_prompt(initial_prompt)
    
    if analysis.get("is_sufficient"):
        print("Prompt is sufficient. Sending directly to deconstruction queue.")
        # Generate a new goal_id for this direct request
        goal_id = f"goal-{uuid.uuid4()}"
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps({"description": initial_prompt, "goal_id": goal_id})
        )
        return {
            "statusCode": 202, # Accepted for processing
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"message": "Goal accepted for processing.", "goal_id": goal_id})
        }
    
    # If the prompt is not sufficient, start a conversation
    print("Prompt is not sufficient. Starting a new conversation.")
    conversation_id = f"conv-{uuid.uuid4()}"
    history = [{"role": "user", "content": initial_prompt}]
    
    return {
        "statusCode": 200, # OK, but requires more info
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps({
            "conversation_id": conversation_id,
            "next_question": analysis.get("clarifying_question"),
            "history": history,
            "status": "AWAITING_USER_INPUT"
        })
    }


def continue_conversation(event):
    """
    Handles subsequent messages in a conversation (POST /goals/conversation/{id}).
    Combines the conversation history and sends the final goal to the SQS queue.
    """
    print("Continuing conversation...")
    body = json.loads(event.get("body", "{}"))
    conversation_id = event.get("pathParameters", {}).get("conversation_id")
    
    history = body.get("history", [])
    new_message = body.get("message", "")
    
    if not new_message:
        raise ValueError("The 'message' field is required for continuing a conversation.")

    # Combine all user inputs into a single, detailed description
    full_description_parts = [msg.get("content") for msg in history if msg.get("role") == "user"]
    full_description_parts.append(new_message)
    full_description = " ".join(full_description_parts)
    
    print(f"Full, combined description: '{full_description}'")
    print("Sending combined goal to deconstruction queue...")
    
    # Send the final, detailed prompt to the SQS queue for processing.
    # The conversation_id now becomes the goal_id.
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({"description": full_description, "goal_id": conversation_id})
    )
    
    return {
        "statusCode": 202, # Accepted for processing
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps({
            "message": "Thank you for the details! Your goal is now being processed.",
            "goal_id": conversation_id # This is the ID the frontend will poll
        })
    }


def analyze_initial_prompt(prompt: str) -> dict:
    """
    Uses a Bedrock LLM to analyze if a prompt is detailed enough to act on.
    If not, it generates a clarifying question.
    """
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"

    analysis_prompt = f"""
    You are an AI assistant that analyzes user requests. Your task is to determine if a user's goal description is detailed enough to be broken down into concrete tasks for creative AI agents (like generating a logo, a slogan, or doing research).

    A detailed request typically mentions the subject (e.g., a company name), the desired outputs (e.g., "logo", "slogan"), and some context (e.g., "coffee brand", "sci-fi game").
    A vague request is very short and lacks these details (e.g., "make me a logo").

    User's Goal: "{prompt}"

    Analyze the goal and respond with ONLY a single, raw JSON object in the following format. Do not add any text before or after the JSON object.
    If the goal is detailed enough, use this format:
    {{
      "is_sufficient": true,
      "clarifying_question": null
    }}

    If the goal is too vague, use this format:
    {{
      "is_sufficient": false,
      "clarifying_question": "<Ask one friendly, open-ended question to get more details. For example: 'That's a great start! Could you tell me a bit more about your project or business?'>"
    }}
    """

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": [{"type": "text", "text": analysis_prompt}]}]
    }
    
    try:
        response = bedrock_runtime.invoke_model(body=json.dumps(request_body), modelId=model_id)
        response_body = json.loads(response.get("body").read())
        generated_text = response_body.get("content")[0].get("text")
        
        json_start_index = generated_text.find('{')
        if json_start_index == -1:
            raise ValueError("No JSON object found in the analysis model's response.")
        
        json_str = generated_text[json_start_index:]
        return json.loads(json_str)
    except (ClientError, json.JSONDecodeError, ValueError) as e:
        print(f"Error during prompt analysis: {e}. Assuming prompt is sufficient.")
        # Fallback to true to avoid breaking the flow on an analysis error
        return {"is_sufficient": True, "clarifying_question": None}