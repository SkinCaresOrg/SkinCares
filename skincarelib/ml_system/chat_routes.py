from fastapi import APIRouter
from pydantic import BaseModel

from skincarelib.ml_system.handler import handle_chat

router = APIRouter()


class ChatRequest(BaseModel):
    message: str



@router.post("/chat")
def chat_endpoint(req: ChatRequest):
    response = handle_chat(req.message)
    return {"response": response}
