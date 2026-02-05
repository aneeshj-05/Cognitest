import json
import requests
from typing import List
from app.schemas import EndpointMetadata, TestCase

# ==========================================
# CONFIGURATION PLACEHOLDERS
# ==========================================
# TODO: Replace these values when you are ready to connect to a real LLM.
LLM_API_KEY = "INSERT_YOUR_API_KEY_HERE"
LLM_ENDPOINT = "https://api.openai.com/v1/chat/completions" # Example: OpenAI
LLM_MODEL = "gpt-4-turbo" 

def construct_system_prompt() -> str:
    """
    Defines the strict behavior rules for the LLM.
    Reference: Design Doc 
    """
    return """
    You are a QA Automation Expert.
    Your task is to generate API test cases based on provided endpoint metadata.
    
    RULES:
    1. Generate only HTTP method-level test cases.
    2. Produce positive and simple negative cases (e.g., missing body, invalid ID).
    3. OUTPUT MUST BE STRICT VALID JSON.
    4. Do not include markdown formatting (like ```json).
    5. Follow the defined schema strictly.
    """

def construct_user_prompt(metadata_list: List[EndpointMetadata]) -> str:
    """
    Feeds the metadata and the required schema to the LLM.
    Reference: Design Doc [cite: 87-98]
    """
    # Convert Pydantic models to a cleaner dict format for the prompt
    data_summary = [m.dict() for m in metadata_list]
    
    return f"""
    Here is the API Endpoint Metadata:
    {json.dumps(data_summary, indent=2)}

    Generate 3-5 test cases for these endpoints.
    
    REQUIRED JSON OUTPUT FORMAT (Array of Objects):
    [
      {{
        "id": "string (unique)",
        "method": "GET | POST | PUT | DELETE",
        "endpoint": "string (e.g. /users/{{id}})",
        "description": "string",
        "headers": {{ "key": "value" }},
        "pathParams": {{ "key": "value" }},
        "queryParams": {{ "key": "value" }},
        "body": {{ "key": "value" }},
        "expectedStatus": number
      }}
    ]
    """

def call_llm_api(system_prompt: str, user_prompt: str) -> str:
    """
    Sends the request to the LLM provider.
    """
    if LLM_API_KEY == "INSERT_YOUR_API_KEY_HERE":
        print("WARNING: No API Key provided. Returning empty list.")
        return "[]"

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2 # Low temperature for deterministic/structured output
    }

    try:
        response = requests.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"LLM Call Failed: {e}")
        return "[]"

def generate_test_cases(metadata_list: List[EndpointMetadata]) -> List[TestCase]:
    """
    Orchestrates the generation process.
    Reference: Design Doc [cite: 103-107]
    """
    system_prompt = construct_system_prompt()
    user_prompt = construct_user_prompt(metadata_list)
    
    # 1. Get raw string from LLM
    raw_response = call_llm_api(system_prompt, user_prompt)
    
    # 2. Clean the response (sometimes LLMs add markdown code blocks)
    clean_json = raw_response.strip().replace("```json", "").replace("```", "")
    
    try:
        # 3. Parse JSON
        parsed_data = json.loads(clean_json)
        
        # 4. Validate against Pydantic Schema
        test_cases = [TestCase(**item) for item in parsed_data]
        return test_cases
        
    except json.JSONDecodeError:
        print("Failed to decode LLM response as JSON.")
        return []
    except Exception as e:
        print(f"Validation Error: {e}")
        return []