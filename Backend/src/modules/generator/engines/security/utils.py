import logging
import asyncio
from typing import Any
import httpx

logger = logging.getLogger(__name__)

async def safe_request(client: httpx.AsyncClient, method: str, url: str, **kwargs: Any) -> httpx.Response:
    """
    Resilient request wrapper that retries on transient errors and 5xx status codes.
    
    Why this is better:
    1. Resilience against cold starts (common in cloud environments).
    2. Resilience against transient 502/503 errors.
    3. Prevents false-negative cascades in security suites.
    """
    retries = 3
    last_resp = None
    
    for attempt in range(retries):
        try:
            resp = await client.request(method, url, **kwargs)
            last_resp = resp
            
            # Retry on 5xx (Server error / Gateway timeout / Cold start)
            # Give Render free tier a bit more time on 503/502
            if resp.status_code in (500, 502, 503, 504) and attempt < retries - 1:
                wait_sec = 1.0 * (attempt + 1)
                if resp.status_code in (502, 503):
                    wait_sec += 1.0 # Extra breath for Render
                
                logger.warning(
                    "Retrying request %s %s due to HTTP %s (Wait %ss, Attempt %d/%d)",
                    method, url, resp.status_code, wait_sec, attempt + 1, retries
                )
                await asyncio.sleep(wait_sec)
                continue
                
            return resp
            
        except (httpx.RequestError, asyncio.TimeoutError) as exc:
            if attempt == retries - 1:
                logger.error("Final request attempt failed for %s %s: %s", method, url, exc)
                if last_resp: return last_resp
                raise
            
            logger.warning(
                "Retrying request %s %s due to network error: %s (Attempt %d/%d)", 
                method, url, exc, attempt + 1, retries
            )
            await asyncio.sleep(0.5 * (attempt + 1))
            
    if last_resp is not None:
        return last_resp
    
    raise httpx.RequestError("Request failed after all retries and no response received")
