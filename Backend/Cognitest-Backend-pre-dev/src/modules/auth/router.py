from fastapi import APIRouter, HTTPException, status, Depends
from .schema import SignupRequest, SignupResponse, LoginRequest, LoginResponse, VerifyOtpRequest, SignupInitialResponse
from . import service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=SignupInitialResponse, status_code=status.HTTP_201_CREATED)
async def signup(data: SignupRequest):
    try:
        return await service.signup(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Signup error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Signup failed")

@router.post("/verify", response_model=SignupResponse)
async def verify_otp(data: VerifyOtpRequest):
    try:
        return await service.verify_otp(data.email, data.otp, data.inviteToken)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Verify OTP error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Verify OTP failed")

@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest):
    try:
        return await service.login(data.email, data.passcode, data.inviteToken)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Login failed")
