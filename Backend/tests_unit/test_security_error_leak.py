import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
from jose import jwt
from src.main import app
from src.config import settings

@pytest.fixture
def auth_headers():
    payload = {"userId": "test-user-id", "tenantId": "test-tenant-id"}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_auth_signup_exception_leak():
    with patch("src.modules.auth.service.signup", side_effect=Exception("Prisma query failed: Table users does not exist")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "email": "test@example.com",
                "name": "Test User",
                "passcode": "password123",
                "company": "Test Company"
            }
            response = await client.post("/api/v1/auth/signup", json=payload)
            assert response.status_code == 500
            data = response.json()
            assert data["detail"] == "Signup failed"
            assert "Prisma" not in data["detail"]

@pytest.mark.asyncio
async def test_auth_verify_exception_leak():
    with patch("src.modules.auth.service.verify_otp", side_effect=Exception("DB Connection Timeout in auth verify")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "email": "test@example.com",
                "otp": "123456"
            }
            response = await client.post("/api/v1/auth/verify", json=payload)
            assert response.status_code == 500
            data = response.json()
            assert data["detail"] == "Verify OTP failed"
            assert "DB Connection" not in data["detail"]

@pytest.mark.asyncio
async def test_auth_login_exception_leak():
    with patch("src.modules.auth.service.login", side_effect=Exception("Internal auth system down")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "email": "test@example.com",
                "passcode": "password123"
            }
            response = await client.post("/api/v1/auth/login", json=payload)
            assert response.status_code == 500
            data = response.json()
            assert data["detail"] == "Login failed"
            assert "system down" not in data["detail"]

@pytest.mark.asyncio
async def test_gateway_exception_leak(auth_headers):
    mock_client = AsyncMock()
    mock_client.request.side_effect = Exception("Connection to internal cluster failed")
    
    mock_async_client_context = AsyncMock()
    mock_async_client_context.__aenter__.return_value = mock_client
    
    with patch("src.routers.gateway.httpx.AsyncClient", return_value=mock_async_client_context):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/gateway/some-endpoint", headers=auth_headers)
            assert response.status_code == 502
            data = response.json()
            assert data["detail"] == "Bad gateway"
            assert "Connection to" not in data["detail"]
