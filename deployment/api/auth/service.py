from typing import Optional

from sqlalchemy.orm import Session
from .models import User
from .security import hash_password, verify_password


def create_user(db: Session, email: str, password: str) -> User:
    """creates a new user in the database after validating the email and hashing the password"""
    email = email.lower().strip()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise ValueError("User with this email already exists")

    hashed = hash_password(password)
    user = User(email=email, hashed_password=hashed)

    # we wrap this in a try-except block to catch any database errors and rollback if something goes wrong
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """authenticates a user by checking if the email exists and the password matches the hashed password in the db"""
    email = email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise ValueError("User not found")
    if not verify_password(password, user.hashed_password):
        raise ValueError("Incorrect password")
    return user


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """querie db with user id and returns the user object if found, otherwise returns None"""
    return db.query(User).filter(User.id == user_id).first()
