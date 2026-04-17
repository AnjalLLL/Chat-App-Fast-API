from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    join = 'join'
    leave = 'leave'
    message = 'message'
    typing = 'typing'
    presence = 'presence'
    error = 'error'


class ChatEvent(BaseModel):
    type: MessageType
    user_id: str
    room_id: str
    text: Optional[str] = None
    timestamp: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp() * 1000))


class UserCreate(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    success: bool
    username: Optional[str] = None
    token: Optional[str] = None
    message: Optional[str] = None


class AuthRequest(BaseModel):
    username: str
    token: str


