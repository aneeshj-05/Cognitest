import os
import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here" or GEMINI_API_KEY == "YOUR_GEMINI_KEY_HERE":
    print("WARNING: GEMINI_API_KEY not configured! Please set it in python-service/.env")
    MODEL = None
else:
    genai.configure(api_key=GEMINI_API_KEY)
    # Using gemini-2.5-flash model
    MODEL = genai.GenerativeModel("gemini-2.5-flash")

PROMPT_TEMPLATE = """
You are an API testing generator. Generate comprehensive test cases for the given API endpoints.

IMPORTANT RULES:
1. For authentication endpoints (register, signup, login, signin), generate tests FIRST
2. For protected endpoints, assume a valid auth token will be available
3. Include both positive tests (expected success) and negative tests (expected failure)
4. Use realistic expected status codes:
   - 200/201 for successful operations
   - 400 for bad requests/validation errors
   - 401 for unauthorized access
   - 403 for forbidden access
   - 404 for not found
   - 409 for conflicts (e.g., duplicate username)

Given API endpoints in JSON:
{endpoints}

Generate test cases in this EXACT JSON format:
[
  {{
    "name": "Descriptive test name",
    "method": "GET|POST|PUT|DELETE|PATCH",
    "path": "/api/path",
    "expected": 200,
    "description": "What this test verifies",
    "category": "positive|negative",
    "priority": "high|medium|low",
    "requiresAuth": true|false
  }}
]

ORDER the tests so that:
1. Register/Create user tests come first
2. Login/Auth tests come second  
3. All other tests come after (these will use the captured auth token)

Return ONLY the JSON array, no other text.
"""

import asyncio
import re
import json

async def generate_testcases_from_gemini(parsed, max_retries=3):
    if MODEL is None:
        raise HTTPException(
            status_code=503,
            detail="Gemini API key not configured. Please set GEMINI_API_KEY in python-service/.env file. Get your key from https://makersuite.google.com/app/apikey"
        )
    
    endpoints = parsed["endpoints"]
    # Convert endpoints to clean JSON string for the prompt
    endpoints_json = json.dumps(endpoints, indent=2)
    prompt = PROMPT_TEMPLATE.format(endpoints=endpoints_json)
    
    print(f"DEBUG: Sending prompt with {len(endpoints)} endpoints")
    print(f"DEBUG: Prompt length: {len(prompt)} chars")

    for attempt in range(max_retries):
        try:
            response = MODEL.generate_content(prompt)
            text = response.text.strip()
            print(f"DEBUG: Received response, length: {len(text)} chars")
            break
        except Exception as e:
            error_msg = str(e)
            print(f"DEBUG: Full error: {error_msg}")
            
            if "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid Gemini API key. Please check your GEMINI_API_KEY in python-service/.env"
                )
            
            # Handle rate limiting with retry
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                # Extract retry delay if available
                retry_match = re.search(r'retry in (\d+\.?\d*)', error_msg.lower())
                wait_time = float(retry_match.group(1)) if retry_match else (15 * (attempt + 1))
                
                if attempt < max_retries - 1:
                    print(f"Rate limited. Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Gemini API rate limit exceeded. Please wait a moment and try again, or use a different API key."
                    )
            
            # For any other error, show the full error message
            raise HTTPException(status_code=500, detail=f"Gemini API error: {error_msg}")

    # Extract JSON from response
    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            print(f"DEBUG: Could not find JSON array in response: {text[:500]}")
            raise HTTPException(status_code=500, detail="Gemini did not return a valid JSON array")
        
        json_text = text[start:end]
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON parse error: {e}")
        print(f"DEBUG: Raw text: {text[:500]}")
        raise HTTPException(status_code=500, detail=f"Failed to parse Gemini response as JSON: {str(e)}")