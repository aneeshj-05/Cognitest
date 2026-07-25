import pytest
from httpx import AsyncClient
from src.config import prisma

class TestAuth:
    @pytest.mark.asyncio
    async def test_signup_success(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/signup", json={
            "email": "test@example.com",
            "name": "Test User",
            "passcode": "password123",
            "company": "Test Inc.",
            "contactNumber": "1234567890"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "Verification code sent to your email" in data["message"]

        # To get a token, we must verify OTP
        user = await prisma.user.find_first(where={"email": "test@example.com"})
        otp = user.otpCode
        
        verify_response = await client.post("/api/v1/auth/verify", json={
            "email": "test@example.com",
            "otp": otp
        })
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert "token" in verify_data
        assert verify_data["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_signup_user_exists(self, client: AsyncClient):
        await client.post("/api/v1/auth/signup", json={
            "email": "test@example.com",
            "name": "Test User",
            "passcode": "password123",
            "company": "Test Inc.",
            "contactNumber": "1234567890"
        })
        # Verify the user so they "exist" in the verified state
        user = await prisma.user.find_first(where={"email": "test@example.com"})
        await prisma.user.update(where={"id": user.id}, data={"isVerified": True})

        # Second signup with same email
        response = await client.post("/api/v1/auth/signup", json={
            "email": "test@example.com",
            "name": "Test User",
            "passcode": "password456",
            "company": "Test Inc 2"
        })
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        await client.post("/api/v1/auth/signup", json={
            "email": "test@example.com",
            "name": "Test User",
            "passcode": "password123",
            "company": "Test Inc."
        })
        
        # Verify the user first
        user = await prisma.user.find_first(where={"email": "test@example.com"})
        await prisma.user.update(where={"id": user.id}, data={"isVerified": True})

        # Then, login
        response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "passcode": "password123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_login_invalid_email(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/login", json={
            "email": "wrong@example.com",
            "passcode": "password123"
        })
        assert response.status_code == 400
        assert "Invalid credentials" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client: AsyncClient):
        await client.post("/api/v1/auth/signup", json={
            "email": "test@example.com",
            "name": "Test User",
            "passcode": "password123",
            "company": "Test Inc."
        })
        # Then, login with wrong password
        response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "passcode": "wrongpassword"
        })
        assert response.status_code == 400
        assert "Invalid credentials" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_otp_lockout(self, client: AsyncClient):
        # Signup first
        signup_response = await client.post("/api/v1/auth/signup", json={
            "email": "lockout@example.com",
            "name": "Lockout User",
            "passcode": "password123",
            "company": "Lockout Co",
            "contactNumber": "1234567890"
        })
        assert signup_response.status_code == 201

        # We try 4 times with invalid OTP
        for i in range(4):
            response = await client.post("/api/v1/auth/verify", json={
                "email": "lockout@example.com",
                "otp": "000000"
            })
            assert response.status_code == 400
            assert "Invalid verification code" in response.json()["detail"]

        # The 5th attempt should lock us out
        response = await client.post("/api/v1/auth/verify", json={
            "email": "lockout@example.com",
            "otp": "000000"
        })
        assert response.status_code == 400
        assert "Too many failed attempts" in response.json()["detail"]

        # Getting the user from DB to find the correct OTP
        user = await prisma.user.find_first(where={"email": "lockout@example.com"})
        otp = user.otpCode

        # Correct OTP should now still fail because of lockout
        response = await client.post("/api/v1/auth/verify", json={
            "email": "lockout@example.com",
            "otp": otp
        })
        assert response.status_code == 400
        assert "Too many failed attempts. Try again in" in response.json()["detail"]

        # Let's manually expire the lockout in the DB to test recovery
        from datetime import datetime, timedelta, timezone
        await prisma.user.update(
            where={"id": user.id},
            data={"otpLockedUntil": datetime.now(timezone.utc) - timedelta(minutes=1)}
        )

        # Now correct OTP should succeed
        response = await client.post("/api/v1/auth/verify", json={
            "email": "lockout@example.com",
            "otp": otp
        })
        assert response.status_code == 200
        assert "token" in response.json()

    @pytest.mark.asyncio
    async def test_generate_otp_is_secure(self):
        from src.modules.auth.service import generate_otp
        otps = [generate_otp() for _ in range(100)]
        for otp in otps:
            assert len(otp) == 6
            assert otp.isdigit()
        # Verify high uniqueness (secrets module randomness)
        assert len(set(otps)) == 100

    @pytest.mark.asyncio
    async def test_otp_expiry(self, client: AsyncClient):
        # Signup first
        signup_response = await client.post("/api/v1/auth/signup", json={
            "email": "expiry@example.com",
            "name": "Expiry User",
            "passcode": "password123",
            "company": "Expiry Co"
        })
        assert signup_response.status_code == 201

        user = await prisma.user.find_first(where={"email": "expiry@example.com"})
        otp = user.otpCode

        # Force OTP expiration in the database
        from datetime import datetime, timedelta, timezone
        await prisma.user.update(
            where={"id": user.id},
            data={"otpExpiry": datetime.now(timezone.utc) - timedelta(seconds=10)}
        )

        # Attempt verification, should be rejected as expired
        response = await client.post("/api/v1/auth/verify", json={
            "email": "expiry@example.com",
            "otp": otp
        })
        assert response.status_code == 400
        assert "expired" in response.json()["detail"]
