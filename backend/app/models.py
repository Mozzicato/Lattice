"""
Database Models
"""
from sqlalchemy import Column, String, Text, Integer, Float, JSON, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


def generate_uuid():
    """Generate a unique ID"""
    return str(uuid.uuid4())


class Document(Base):
    """Document model"""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    raw_text = Column(Text)
    doc_metadata = Column(JSON)  # Renamed from 'metadata' to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    equations = relationship("Equation", back_populates="document", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="document", cascade="all, delete-orphan")


class Equation(Base):
    """Equation model"""
    __tablename__ = "equations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    latex = Column(Text, nullable=False)
    context = Column(Text)
    position = Column(Integer)
    section_title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="equations")
    analyses = relationship("EquationAnalysis", back_populates="equation", cascade="all, delete-orphan")
    simulations = relationship("Simulation", back_populates="equation", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="equation", cascade="all, delete-orphan")


class EquationAnalysis(Base):
    """Equation analysis model"""
    __tablename__ = "equation_analyses"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    equation_id = Column(String, ForeignKey("equations.id"), nullable=False)
    variables = Column(JSON)
    steps = Column(JSON)
    explanation = Column(Text)
    complexity_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    equation = relationship("Equation", back_populates="analyses")


class Simulation(Base):
    """Simulation model"""
    __tablename__ = "simulations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    equation_id = Column(String, ForeignKey("equations.id"), nullable=False)
    variables = Column(JSON)
    ranges = Column(JSON)
    plot_config = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    equation = relationship("Equation", back_populates="simulations")


class Question(Base):
    """Question model"""
    __tablename__ = "questions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    equation_id = Column(String, ForeignKey("equations.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String)
    options = Column(JSON)
    correct_answer = Column(String)
    explanation = Column(Text)
    difficulty = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    equation = relationship("Equation", back_populates="questions")


class Session(Base):
    """User session model"""
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    interaction_log = Column(JSON)
    
    # Relationships
    document = relationship("Document", back_populates="sessions")
