import json
import requests
from typing import List
from app.schemas import EndpointMetadata, TestCase

# ==========================================
# CONFIGURATION PLACEHOLDERS
# ==========================================
# TODO: Replace these values when you are ready to connect to a real LLM.
LLM_API_KEY = "AIzaSyC-eWV0-XEBrOJyV0muDDFrmxhRH30yqT8"
LLM_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
LLM_MODEL = "gemini-2.5-flash"

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
    data_summary = [m.dict() for m in metadata_list]
    
    return f"""
API Endpoints: {json.dumps(data_summary, indent=2)}

Generate exactly 3 test cases. Keep descriptions short.

Return ONLY valid JSON array:
[
  {{
    "id": "test1",
    "method": "GET",
    "endpoint": "/users/1",
    "description": "Get user",
    "headers": {{}},
    "pathParams": {{"id": "1"}},
    "queryParams": {{}},
    "body": {{}},
    "expectedStatus": 200
  }}
]
"""

def call_llm_api(system_prompt: str, user_prompt: str) -> str:
    """
    Sends the request to the Gemini API.
    """
    if LLM_API_KEY == "INSERT_YOUR_API_KEY_HERE":
        print("WARNING: No API Key provided. Returning empty list.")
        return "[]"

    headers = {
        "Content-Type": "application/json"
    }
    
    # Combine system and user prompts for Gemini
    combined_prompt = f"{system_prompt}\n\n{user_prompt}"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": combined_prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096
        }
    }

    try:
        url = f"{LLM_ENDPOINT}?key={LLM_API_KEY}"
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print(f"Unexpected API response format: {data}")
            return "[]"
            
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
        
    except json.JSONDecodeError as e:
        print(f"Failed to decode LLM response as JSON: {e}")
        print(f"Response was: {clean_json[:200]}...")
        return []
    except Exception as e:
        print(f"Validation Error: {e}")
        return []