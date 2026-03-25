from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from . import schemas, service, security
from deployment.api.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=schemas.UserRead)
def register_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(service.User).filter(service.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = service.create_user(db, payload.email, payload.password)
    return user

@router.post("/login")
def login_user(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = service.authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = security.create_access_token({"user_id": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}