from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import uuid

from deployment.api.db.session import get_db
from .service import get_user_by_id
from .security import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
):
    """this extracts the user back from the token and returns the user object"""
    if token is None:
        raise HTTPException(status_code=401, detail="Missing token")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = get_user_by_id(db, user_id)  # queries db for user with that id
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def get_current_user_optional(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
):
    """returns current user if auth is valid, None otherwise (for optional auth endpoints)"""
    if token is None:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return None

    user = get_user_by_id(db, user_id)
    return user
