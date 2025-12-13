from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class MessageBase(BaseModel):
    role: str
    content: str
    message_type: str = "text"

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    session_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class SessionBase(BaseModel):
    title: Optional[str] = None

class SessionCreate(SessionBase):
    document_id: Optional[int] = None

class Session(SessionBase):
    id: int
    created_at: datetime
    messages: List[Message] = []

    class Config:
        from_attributes = True

class DocumentBase(BaseModel):
    filename: str

class Document(DocumentBase):
    id: int
    upload_date: datetime
    status: str

    class Config:
        from_attributes = True
