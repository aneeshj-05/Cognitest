import asyncio
import sys, os
sys.path.insert(0, os.getcwd())
from src.modules.generator.ai.generators.security_generator import generate_security_tests_ai

spec = {
    "info": {"title": "Test API"},
    "paths": {
        "/items/{id}": {
            "get": {
                "parameters": [{"name": "id", "in": "path", "required": True}]
            }
        }
    }
}

async def main():
    cases, _ = await generate_security_tests_ai(spec)
    print("RETURNED CASES:", len(cases))
    import json
    # print(json.dumps(cases, indent=2))

asyncio.run(main())
