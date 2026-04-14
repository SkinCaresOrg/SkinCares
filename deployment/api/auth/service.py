from typing import Optional

from sqlalchemy.orm import Session

from .models import User
from .security import hash_password, verify_password


def create_user(db: Session, email: str, password: str) -> User:
    """Create a new user with validated email and hashed password"""
    email = email.lower().strip()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise ValueError("User with this email already exists")

    hashed = hash_password(password)
    user = User(email=email, hashed_password=hashed)

    # Wrap in try-except to catch database errors and rollback on failure
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user by email and password verification"""
    email = email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise ValueError("User not found")
    if not verify_password(password, user.hashed_password):
        raise ValueError("Incorrect password")
    return user


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Get user by ID, returns None if not found"""
    return db.query(User).filter(User.id == user_id).first()
