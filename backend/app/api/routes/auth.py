from fastapi import APIRouter, HTTPException

from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    if not payload.password:
        raise HTTPException(status_code=400, detail="Password is required")
    token = create_access_token(payload.email, {"role": "manager"})
    return TokenResponse(access_token=token)
