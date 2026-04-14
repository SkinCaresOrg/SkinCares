from typing import Any, Dict, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from skincarelib.ml_system.handler import handle_chat

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    profile: Optional[Dict[str, Any]] = None

@router.post("/chat")
def chat_endpoint(req: ChatRequest):
    response, _ = handle_chat(req.message, profile=req.profile)
    return {"response": response}
