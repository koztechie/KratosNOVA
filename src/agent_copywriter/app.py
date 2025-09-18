"""
Lambda function for the Copywriter Agent with a Self-Correction loop.

This function is invoked by the orchestrator to execute TEXT contracts. It generates
content, critiques its own work, and re-generates if the quality is below a
certain threshold before submitting the final result.
"""
import json
import os
import uuid
import boto3
import requests
from botocore.exceptions import ClientError

# Initialize clients
bedrock_runtime = boto3.client(service_name="bedrock-runtime")
API_BASE_URL = os.environ.get("API_BASE_URL")

def handler(event, context):
    """
    Main handler for the Copywriter Agent with a self-correction loop.
    """
    _ = context
    print(f"Copywriter Agent triggered with event: {json.dumps(event)}")

    contract_id = event.get("contract_id")
    try:
        prompt = event.get("prompt")
        if not prompt or not contract_id:
            raise ValueError("Input event must include 'prompt' and 'contract_id'.")

        # --- SELF-CORRECTION LOOP ---
        final_slogans = []
        is_good_enough = False
        attempts = 0
        max_attempts = 2  # Max 2 full generation cycles

        while not is_good_enough and attempts < max_attempts:
            attempts += 1
            print(f"Generation cycle attempt #{attempts}")

            # 1. Generate slogans
            print("Step 1: Generating slogans...")
            generated_slogans = generate_and_parse_slogans(prompt)
            if not generated_slogans:
                print("Generation returned no slogans, retrying...")
                continue
            
            # 2. Self-Critique the generated slogans
            print("Step 2: Self-critiquing slogans...")
            critique = critique_slogans(prompt, generated_slogans)
            
            quality_score = critique.get("quality_score", 0)
            print(f"Received quality score: {quality_score}/10")

            if quality_score >= 7:
                is_good_enough = True
                final_slogans = generated_slogans
                print("Slogans passed quality check.")
            else:
                print("Slogans failed quality check. Rerunning generation.")
                # Modify the prompt for the next attempt to encourage improvement
                justification = critique.get('justification', 'No specific feedback.')
                prompt += (f"\n\nYour previous attempt was rated {quality_score}/10. "
                           f"Critique: {justification}. "
                           "Please generate a much better, more creative set of slogans based on this feedback.")

        if not final_slogans:
            raise ValueError(f"Agent failed to generate high-quality slogans after {max_attempts} attempts.")

        # 3. Submit the best result to the marketplace
        # We submit the first slogan as an example
        submission_text = final_slogans[0] if final_slogans else "No slogan generated."
        print(f"Step 3: Submitting final result to marketplace: '{submission_text}'")
        submit_work(contract_id, submission_text)
        print("Submission successful.")
        
        return {"status": "success"}

    except (ClientError, ValueError, requests.exceptions.RequestException) as e:
        print(f"Copywriter Agent failed for contract {contract_id}. Error: {e}")
        raise e

def critique_slogans(original_prompt: str, slogans: list) -> dict:
    """
    Uses Claude 3 Haiku to evaluate its own generated slogans.
    """
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    slogans_str = json.dumps(slogans)

    prompt = f"""
    You are a Quality Assurance critic. Your task is to evaluate a list of generated slogans based on an original request.

    **Original Request:** "{original_prompt}"

    **Generated Slogans to Evaluate:**
    {slogans_str}

    **Your Instructions:**
    1.  Assess the slogans based on creativity, relevance to the request, and overall quality.
    2.  Provide a quality score from 1 (very bad) to 10 (perfect).
    3.  Provide a brief justification for your score.

    Respond with ONLY a single, raw JSON object in the following format:
    {{
      "quality_score": <your_score_as_a_number>,
      "justification": "<Your brief justification>"
    }}
    """
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    }
    
    try:
        response = bedrock_runtime.invoke_model(body=json.dumps(request_body), modelId=model_id)
        response_body = json.loads(response.get("body").read())
        generated_text = response_body.get("content")[0].get("text")
        
        json_start_index = generated_text.find('{')
        if json_start_index == -1:
            return {"quality_score": 1, "justification": "Failed to parse critique response."}
        
        json_str = generated_text[json_start_index:]
        return json.loads(json_str)
    except (ClientError, json.JSONDecodeError):
        print("Warning: Could not parse critique response. Assuming low quality.")
        return {"quality_score": 1, "justification": "Could not parse the critique model's response."}

def generate_and_parse_slogans(prompt: str, max_retries: int = 2) -> list:
    """
    Generates text and attempts to parse it as JSON, with retries.
    """
    for attempt in range(max_retries):
        print(f"Attempt {attempt + 1} of {max_retries} to generate and parse JSON.")
        generated_text = generate_text(prompt)
        try:
            start_index = generated_text.find('[')
            end_index = generated_text.rfind(']')
            if start_index != -1 and end_index != -1:
                json_str = generated_text[start_index:end_index+1]
                parsed_json = json.loads(json_str)
                if isinstance(parsed_json, list):
                    return parsed_json
        except json.JSONDecodeError:
            print(f"Failed to decode JSON from model response: '{generated_text}', retrying...")
            continue
            
    raise ValueError(f"Failed to get a valid JSON array from the model after {max_retries} attempts.")

def generate_text(prompt: str) -> str:
    """
    Invokes the Anthropic Claude 3 Haiku model to generate text.
    """
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    
    hardened_prompt = f"""
    You are an AI assistant that ONLY responds with JSON.
    Your task is to perform the user's request and format the entire output as a single, raw JSON object.
    Do not under any circumstances include any explanatory text, markdown, or any characters before or after the JSON object.

    User Request: "{prompt}"

    Your JSON response must be a JSON array of strings.
    """

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": [{"type": "text", "text": hardened_prompt}]}]
    }
    try:
        response = bedrock_runtime.invoke_model(
            body=json.dumps(request_body),
            modelId=model_id,
            accept="application/json",
            contentType="application/json"
        )
        response_body = json.loads(response.get("body").read())
        generated_text = response_body.get("content")[0].get("text")
        print(f"Raw model output: {generated_text}")
        return generated_text
    except Exception as e:
        raise ValueError(f"Error in generate_text: {e}") from e

def submit_work(contract_id: str, submission_data: str):
    """Submits the completed work via the API."""
    submission_url = f"{API_BASE_URL}/contracts/{contract_id}/submissions"
    payload = {
        "agent_id": f"agent-copywriter-{uuid.uuid4()}",
        "submission_data": submission_data
    }
    print(f"Submitting to {submission_url} with payload: {json.dumps(payload)}")
    response = requests.post(submission_url, json=payload, timeout=10)
    response.raise_for_status()
    print(f"Submission API response: {response.json()}")
