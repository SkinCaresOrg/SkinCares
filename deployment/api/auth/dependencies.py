from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from deployment.api.db.session import get_db
from .service import get_user_by_id

def get_current_user(user_id: str, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user