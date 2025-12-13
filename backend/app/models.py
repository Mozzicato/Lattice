from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    # Status: uploaded, processing, ready, error
    status = Column(String, default="uploaded")
    
    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="document")

class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    page_number = Column(Integer)
    image_path = Column(String) # Path to the original page image
    
    # Content
    ocr_text = Column(Text, nullable=True)
    latex_content = Column(Text, nullable=True)
    
    # Beautification
    beautified_text = Column(Text, nullable=True)
    beautified_image_path = Column(String, nullable=True)
    
    document = relationship("Document", back_populates="pages")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    title = Column(String, nullable=True)
    
    document = relationship("Document", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    role = Column(String) # user, assistant, system
    content = Column(Text)
    message_type = Column(String, default="text") # text, audio, image
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # For "I'm Lost" or specific context references
    context_data = Column(Text, nullable=True) 

    session = relationship("Session", back_populates="messages")
