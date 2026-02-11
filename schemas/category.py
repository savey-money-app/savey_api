"""Category schemas for requests and responses"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
from uuid import UUID


class CategoryCreate(BaseModel):
    """Schema for creating a new category"""
    title: str = Field(..., min_length=1, max_length=100)
    title_ru: Optional[str] = Field(None, min_length=1, max_length=100)


class CategoryUpdate(BaseModel):
    """Schema for updating a category"""
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    title_ru: Optional[str] = Field(None, min_length=1, max_length=100)


class CategoryResponse(BaseModel):
    """Schema for category response"""
    id: UUID
    title: str
    title_ru: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
