"""
Learning Session API Endpoints
Interactive learning after document has been fully processed
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import logging

from app.database import get_db
from app.models import Document, Equation, EquationAnalysis, Session as SessionModel
from app.services.llm_client import LLMClient
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


# Schemas
class SessionStartRequest(BaseModel):
    """Request to start a learning session"""
    document_id: str
    learning_goals: Optional[List[str]] = None


class SessionResponse(BaseModel):
    """Learning session info"""
    session_id: str
    document_id: str
    status: str
    current_step: str
    progress: Dict[str, Any]


class QuestionRequest(BaseModel):
    """Ask a question about the document"""
    question: str
    context: Optional[str] = None


class QuestionResponse(BaseModel):
    """Response to user question"""
    answer: str
    related_equations: List[str] = []
    references: List[str] = []


class ConceptExplanationRequest(BaseModel):
    """Request explanation of a concept"""
    concept: str


@router.post("/sessions/start", response_model=SessionResponse)
async def start_learning_session(
    request: SessionStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start an interactive learning session for a processed document
    """
    # Check if document exists and is ready
    document = db.query(Document).filter(Document.id == request.document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    metadata = document.doc_metadata or {}
    if not metadata.get("processing_complete"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document is still being processed. Please wait for processing to complete."
        )
    
    # Create session
    session = SessionModel(
        document_id=request.document_id,
        interaction_log={
            "learning_goals": request.learning_goals or [],
            "concepts_covered": [],
            "equations_studied": [],
            "questions_asked": 0
        }
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # Get document stats
    equation_count = db.query(Equation).filter(Equation.document_id == request.document_id).count()
    
    logger.info(f"Started learning session {session.id} for document {request.document_id}")
    
    return SessionResponse(
        session_id=session.id,
        document_id=request.document_id,
        status="active",
        current_step="overview",
        progress={
            "equations_total": equation_count,
            "equations_studied": 0,
            "concepts_total": len(metadata.get("concepts", [])),
            "concepts_covered": 0
        }
    )


@router.get("/sessions/{session_id}/overview")
async def get_session_overview(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get overview of the document to start learning
    Returns: key concepts, equation list, sections
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    document = db.query(Document).filter(Document.id == session.document_id).first()
    equations = db.query(Equation).filter(Equation.document_id == session.document_id).all()
    
    metadata = document.doc_metadata or {}
    
    return {
        "document": {
            "id": document.id,
            "filename": document.filename,
            "character_count": metadata.get("character_count", 0)
        },
        "concepts": metadata.get("concepts", []),
        "sections": metadata.get("sections", []),
        "equations": [
            {
                "id": eq.id,
                "latex": eq.latex,
                "section": eq.section_title,
                "position": eq.position
            }
            for eq in equations
        ],
        "ready_for_learning": True
    }


@router.post("/sessions/{session_id}/ask", response_model=QuestionResponse)
async def ask_question(
    session_id: str,
    request: QuestionRequest,
    db: Session = Depends(get_db)
):
    """
    Ask a question about the document content
    AI will answer using document context
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    document = db.query(Document).filter(Document.id == session.document_id).first()
    equations = db.query(Equation).filter(Equation.document_id == session.document_id).all()
    
    # Build context from document
    llm_client = LLMClient()
    
    # Get relevant equations
    relevant_equations = []
    for eq in equations[:5]:  # Limit to top 5 for context
        relevant_equations.append(f"{eq.latex} (from {eq.section_title})")
    
    prompt = f"""You are a helpful AI tutor. A student is studying this document and has a question.

Document: {document.filename}
Content excerpt: {document.raw_text[:2000]}

Equations in document:
{chr(10).join(relevant_equations)}

Student's question: {request.question}

Provide a clear, educational answer. Reference specific equations or concepts from the document when relevant.
"""
    
    answer = llm_client.complete(prompt, temperature=0.7, max_tokens=1500)
    
    # Update session interaction_log
    if session.interaction_log is None:
        session.interaction_log = {}
    session.interaction_log["questions_asked"] = session.interaction_log.get("questions_asked", 0) + 1
    db.commit()
    
    return QuestionResponse(
        answer=answer,
        related_equations=[eq.id for eq in equations if request.question.lower() in (eq.section_title or "").lower()][:3],
        references=[]
    )


@router.get("/sessions/{session_id}/equation/{equation_id}")
async def study_equation(
    session_id: str,
    equation_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed view of a specific equation for study
    Includes: analysis, variables, simulation config, practice questions
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    equation = db.query(Equation).filter(Equation.id == equation_id).first()
    
    if not equation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equation not found"
        )
    
    # Get analysis
    analysis = db.query(EquationAnalysis).filter(EquationAnalysis.equation_id == equation_id).first()
    
    # Update session progress
    if session.interaction_log is None:
        session.interaction_log = {}
    equations_studied = session.interaction_log.get("equations_studied", [])
    if equation_id not in equations_studied:
        equations_studied.append(equation_id)
        session.interaction_log["equations_studied"] = equations_studied
        db.commit()
    
    result = {
        "equation": {
            "id": equation.id,
            "latex": equation.latex,
            "context": equation.context,
            "section": equation.section_title
        },
        "ready_for_simulation": False,
        "practice_questions_available": False
    }
    
    if analysis:
        result["analysis"] = {
            "explanation": analysis.explanation,
            "variables": analysis.variables,
            "complexity": analysis.complexity_score
        }
        result["ready_for_simulation"] = len(analysis.variables) > 0
    
    return result


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Mark learning session as complete
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session.interaction_log is None:
        session.interaction_log = {}
    session.interaction_log["status"] = "completed"
    db.commit()
    
    return {
        "session_id": session_id,
        "status": "completed",
        "summary": {
            "equations_studied": len(session.interaction_log.get("equations_studied", [])),
            "questions_asked": session.interaction_log.get("questions_asked", 0),
            "concepts_covered": len(session.interaction_log.get("concepts_covered", []))
        }
    }
