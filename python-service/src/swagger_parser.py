import httpx
from fastapi import HTTPException

async def parse_swagger(swagger_url: str):
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(swagger_url)
            resp.raise_for_status()
            
            content_type = resp.headers.get("content-type", "")
            if "json" not in content_type and "yaml" not in content_type:
                raise HTTPException(
                    status_code=400,
                    detail=f"URL did not return JSON/YAML. Got content-type: {content_type}. Make sure you're using the raw Swagger JSON URL."
                )
            
            try:
                spec = resp.json()
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to parse response as JSON. Make sure the URL points to a valid Swagger/OpenAPI JSON spec."
                )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch Swagger spec: {e}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to URL: {e}")

    base_url = ""
    if "servers" in spec and spec["servers"]:
        base_url = spec["servers"][0]["url"]

    endpoints = []
    for path, methods in spec.get("paths", {}).items():
        for method, details in methods.items():
            endpoints.append({
                "method": method.upper(),
                "path": path,
                "summary": details.get("summary", "")
            })

    return {
        "baseUrl": base_url,
        "endpoints": endpoints
    }