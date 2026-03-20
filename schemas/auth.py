"""Authentication schemas for login, register, and tokens"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from schemas.user import validate_currency_code


class RegisterRequest(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    currency: str
    preferred_language: str

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return validate_currency_code(v)


class LoginRequest(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str = "bearer"
