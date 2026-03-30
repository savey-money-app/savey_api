"""Authentication routes for login, register, and user profile"""
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from core.config import settings
from core.database import get_db
from schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from schemas.user import UserResponse, UserWithBalance
from services.user_service import create_user, get_user_by_email, get_user_by_id, create_user_profile
from services.transaction_service import calculate_user_balance
from services.auth_service import verify_password, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if email already exists
    existing_user = get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = create_user(db, request)

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login a user"""
    # Get user by email
    user = get_user_by_email(db, request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(access_token=access_token)


def _decode_token(token: str) -> Optional[dict]:
    """
    Decode a JWT, accepting tokens from both savey_auth (JWT_SECRET)
    and legacy FastAPI tokens (SECRET_KEY). Deduplicates if both are equal.
    """
    from jose import jwt as jose_jwt, JWTError
    jwt_secret = settings.JWT_SECRET or settings.SECRET_KEY
    for secret in dict.fromkeys([jwt_secret, settings.SECRET_KEY]):
        try:
            return jose_jwt.decode(token, secret, algorithms=[settings.ALGORITHM])
        except JWTError:
            continue
    return None


def get_jwt_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Return the full decoded JWT payload."""
    payload = _decode_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return payload


def get_current_user(
    payload: dict = Depends(get_jwt_payload),
) -> str:
    """Dependency to get current user ID from JWT token (Better Auth or legacy)"""
    return payload["sub"]


security_optional = HTTPBearer(auto_error=False)


def get_user_internal_or_jwt(
    x_internal_token: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    db: Session = Depends(get_db),
) -> str:
    """
    Auth dependency that accepts either:
    - Internal service token (X-Internal-Token + X-User-ID headers), or
    - Regular JWT Bearer token
    """
    # Internal service path
    if x_internal_token and x_internal_token == settings.INTERNAL_API_TOKEN:
        if not x_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-User-ID header required with internal token",
            )
        return x_user_id

    # JWT path
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    return user_id


@router.get("/me", response_model=UserWithBalance)
def get_current_user_profile(
    jwt_payload: dict = Depends(get_jwt_payload),
    db: Session = Depends(get_db)
):
    """Get current user profile with live balance. Lazy-creates profile for Better Auth users."""
    current_user_id: str = jwt_payload["sub"]
    email: Optional[str] = jwt_payload.get("email")

    user = get_user_by_id(db, current_user_id)
    if not user:
        # First login via Better Auth (email/password or OAuth) — create profile record
        user = create_user_profile(db, current_user_id, email=email)

    balance = calculate_user_balance(
        db, current_user_id,
        monthly_limit=user.monthly_limit,
        daily_limit=user.daily_limit,
    )
    return UserWithBalance(user=UserResponse.model_validate(user), balance=balance)
