"""User schemas for requests and responses"""
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from datetime import datetime
from typing import Optional
from uuid import UUID

# ISO 4217 currency codes (common currencies)
VALID_CURRENCIES = {
    "USD", "EUR", "GBP", "JPY", "CNY", "INR", "CAD", "AUD", "CHF", "HKD",
    "SGD", "SEK", "KRW", "NOK", "NZD", "MXN", "TWD", "ZAR", "BRL", "DKK",
    "PLN", "THB", "ILS", "IDR", "CZK", "AED", "TRY", "HUF", "CLP", "SAR",
    "PHP", "MYR", "COP", "RUB", "RON", "PEN", "BHD", "BGN", "ARS", "KZT",
    "UAH", "EGP", "VND", "PKR", "IQD", "QAR", "KWD", "NGN", "BDT", "GEL",
}


def validate_currency_code(v: str) -> str:
    """Validate ISO 4217 currency code"""
    if v.upper() not in VALID_CURRENCIES:
        raise ValueError(f"Invalid ISO 4217 currency code: {v}")
    return v.upper()


class UserCreate(BaseModel):
    """Schema for creating a new user"""
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    currency: str

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return validate_currency_code(v)


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    currency: Optional[str] = None
    monthly_limit: Optional[int] = None
    daily_limit: Optional[int] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_currency_code(v)


class UserResponse(BaseModel):
    """Schema for user response"""
    id: UUID
    email: str
    full_name: Optional[str] = None
    currency: str
    monthly_limit: Optional[int] = None
    daily_limit: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserBalance(BaseModel):
    """Schema for user balance"""
    balance: float
    monthly_spending: float
    monthly_limit: float = 0.0
    daily_spending: float
    daily_limit: float = 0.0


class UserWithBalance(BaseModel):
    """User profile combined with live balance"""
    user: UserResponse
    balance: UserBalance