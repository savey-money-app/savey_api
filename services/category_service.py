"""Category service for category CRUD operations"""
from sqlalchemy.orm import Session
from models.category import Category
from schemas.category import CategoryCreate, CategoryUpdate
from typing import List, Optional


def get_all_categories(db: Session) -> List[Category]:
    """Get all categories"""
    return db.query(Category).order_by(Category.title).all()


def get_category_by_id(db: Session, category_id: str) -> Optional[Category]:
    """Get category by ID"""
    return db.query(Category).filter(Category.id == category_id).first()


def get_category_by_title(db: Session, title: str) -> Optional[Category]:
    """Get category by title"""
    return db.query(Category).filter(Category.title == title).first()


def create_category(db: Session, category_data: CategoryCreate) -> Category:
    """Create a new category"""
    category = Category(**category_data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category_id: str, category_data: CategoryUpdate) -> Optional[Category]:
    """Update a category"""
    category = get_category_by_id(db, category_id)
    if not category:
        return None

    category.title = category_data.title
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category_id: str) -> bool:
    """Delete a category (will fail if transactions reference it)"""
    category = get_category_by_id(db, category_id)
    if not category:
        return False

    db.delete(category)
    db.commit()
    return True
