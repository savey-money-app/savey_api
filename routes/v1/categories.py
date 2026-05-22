"""Category management routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db
from schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse
from services.category_service import (
    get_all_categories,
    get_category_by_id,
    get_category_by_title,
    create_category,
    update_category,
    delete_category
)
from routes.v1.auth import get_user_internal_or_jwt

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=List[CategoryResponse])
def list_categories(current_user_id: str = Depends(get_user_internal_or_jwt), db: Session = Depends(get_db)):
    """Get all categories (public endpoint)"""
    return get_all_categories(db)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: str, current_user_id: str = Depends(get_user_internal_or_jwt), db: Session = Depends(get_db)):
    """Get a specific category by ID"""
    category = get_category_by_id(db, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    return category


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_new_category(
    category_data: CategoryCreate,
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db)
):
    """Create a new category (requires authentication)"""
    # Check if category with same title exists
    existing = get_category_by_title(db, category_data.title)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this title already exists"
        )

    return create_category(db, category_data)


@router.put("/{category_id}", response_model=CategoryResponse)
def update_existing_category(
    category_id: str,
    category_data: CategoryUpdate,
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db)
):
    """Update a category (requires authentication)"""
    # Check if another category with same title exists
    existing = get_category_by_title(db, category_data.title)
    if existing and str(existing.id) != category_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this title already exists"
        )

    category = update_category(db, category_id, category_data)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_category(
    category_id: str,
    current_user_id: str = Depends(get_user_internal_or_jwt),
    db: Session = Depends(get_db)
):
    """Delete a category (requires authentication, will fail if transactions use it)"""
    try:
        success = delete_category(db, category_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category that is used by transactions"
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    return None
