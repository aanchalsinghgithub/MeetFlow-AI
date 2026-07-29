from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class CurrentUser(BaseModel):
    user_id: int
    organization_id: int
    email: str | None = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8")
        )
    except ValueError:
        # Malformed/foreign hash format - treat as "does not match" rather
        # than raising, so a bad stored hash can't crash login.
        return False


def hash_password(password: str) -> str:
    # bcrypt hard-caps input at 72 bytes; truncate defensively so callers
    # never hit the "password cannot be longer than 72 bytes" ValueError.
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise credentials_error from exc

    user_id = payload.get("user_id")
    organization_id = payload.get("organization_id")
    if user_id is None or organization_id is None:
        raise credentials_error

    return CurrentUser(
        user_id=int(user_id),
        organization_id=int(organization_id),
        email=payload.get("sub"),
    )
