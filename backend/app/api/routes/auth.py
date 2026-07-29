from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.entities import Organization, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter()


def _token_for(user: User) -> TokenResponse:
    token = create_access_token(
        user.email,
        {
            "user_id": user.id,
            "organization_id": user.organization_id,
            "role": user.role,
        },
    )
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing_user = db.query(User).filter(User.email == payload.email).one_or_none()
    if existing_user:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    company_name = payload.company_name.strip()
    if not company_name:
        raise HTTPException(status_code=400, detail="Company name is required")

    organization = db.query(Organization).filter(Organization.name == company_name).one_or_none()
    if organization is None:
        organization = Organization(name=company_name)
        db.add(organization)
        db.flush()

    user = User(
        organization_id=organization.id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role="manager",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_for(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token_for(user)
