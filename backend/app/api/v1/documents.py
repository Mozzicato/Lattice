"""
Document Management API Endpoints
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging
import shutil
from pathlib import Path

from app.database import get_db
from app.schemas import DocumentResponse, DocumentWithEquations, UploadResponse
from app.services.document_processor import DocumentProcessor
from app.services.llm_client import LLMClient
from app.models import Document, Equation as EquationModel

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/documents/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a document (PDF or text file) for comprehensive processing.
    
    This endpoint:
    1. Validates and saves the uploaded file
    2. Extracts ALL text content
    3. Identifies ALL equations with context
    4. Analyzes equations with AI (Gemini 2.5 Flash)
    5. Extracts key concepts and document structure
    6. Prepares document for interactive learning
    """
    try:
        # Initialize LLM client and processor
        llm_client = LLMClient()
        processor = DocumentProcessor(llm_client)
        
        # Validate file
        validation = processor.parser.validate_file(file)
        if not validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation["error"]
            )
        
        # Save file temporarily
        from app.config import settings
        upload_path = Path(settings.UPLOAD_DIR) / file.filename
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        
        with upload_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create document record
        document = Document(filename=file.filename)
        db.add(document)
        db.commit()
        db.refresh(document)
        
        logger.info(f"Document uploaded: {document.id}, starting comprehensive processing...")
        
        # Process entire document comprehensively
        results = processor.process_document(
            file_path=str(upload_path),
            document=document,
            db=db
        )
        
        logger.info(f"Document processing results: {results}")
        
        return UploadResponse(
            document_id=document.id,
            status=results["status"],
            estimated_time=0,
            poll_url=f"/api/v1/documents/{document.id}"
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/documents/{document_id}", response_model=DocumentWithEquations)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    """
    Get document details by ID
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """
    Delete a document and all associated data
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    
    db.delete(document)
    db.commit()
    
    logger.info(f"Document deleted: {document_id}")
    return None


@router.get("/documents/{document_id}/equations")
async def get_document_equations(document_id: str, db: Session = Depends(get_db)):
    """
    Get all equations from a document
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    
    return document.equations
