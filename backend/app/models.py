from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# If the module is reloaded (during development or repeated imports),
# ensure prior table metadata entries are cleared to avoid
# "Table ... is already defined" errors from SQLAlchemy.
try:
    Base.metadata.clear()
except Exception:
    pass


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="uploaded")

    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="document")
    jobs = relationship("Job", back_populates="document", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    page_number = Column(Integer)
    image_path = Column(String)  # Path to the original page image

    ocr_text = Column(Text, nullable=True)
    latex_content = Column(Text, nullable=True)

    beautified_text = Column(Text, nullable=True)
    beautified_image_path = Column(String, nullable=True)

    document = relationship("Document", back_populates="pages")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    title = Column(String, nullable=True)

    document = relationship("Document", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    role = Column(String)  # user, assistant, system
    content = Column(Text)
    message_type = Column(String, default="text")  # text, audio, image
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    context_data = Column(Text, nullable=True)

    session = relationship("Session", back_populates="messages")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    status = Column(String, default="queued")  # queued, running, completed, error
    progress = Column(Integer, default=0)  # 0-100
    message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    document = relationship("Document", back_populates="jobs")
