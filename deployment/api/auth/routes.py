from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import schemas, service, security
from deployment.api.db.session import get_db
from .dependencies import get_current_user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserRead)
def register_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    """endpoint to register a new user"""
    try:
        user = service.create_user(db, payload.email, payload.password)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/login", response_model=schemas.Token)
def login_user(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    """endpoint to authenticate a user and return an access token"""
    try:
        user = service.authenticate_user(db, payload.email, payload.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    token = security.create_access_token({"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=schemas.UserRead)
def read_current_user(current_user: schemas.UserRead = Depends(get_current_user)):
    """endpoint to get the current authenticated user's information"""
    return current_user
