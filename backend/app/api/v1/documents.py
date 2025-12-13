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
    2. Returns immediately with document ID
    3. Processing happens in background (check status via poll_url)
    """
    import asyncio
    
    try:
        # Initialize processor for validation only
        from app.services.document_parser import DocumentParser
        parser = DocumentParser()
        
        # Validate file
        validation = parser.validate_file(file)
        if not validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation["error"]
            )
        
        # Save file asynchronously
        from app.config import settings
        import aiofiles
        
        upload_path = Path(settings.UPLOAD_DIR) / file.filename
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(upload_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # Read in 1MB chunks
                await out_file.write(content)
        
        # Create document record with processing status
        document = Document(
            filename=file.filename,
            doc_metadata={"status": "processing", "page_count": 0}
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        logger.info(f"Document uploaded: {document.id}, starting background processing...")
        
        # Start background processing
        asyncio.create_task(_process_document_background(
            document_id=document.id,
            file_path=str(upload_path)
        ))
        
        return UploadResponse(
            document_id=document.id,
            status="processing",
            estimated_time=60,
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


async def _process_document_background(document_id: str, file_path: str):
    """Background task to process document without blocking upload response"""
    from app.database import SessionLocal
    
    db = SessionLocal()
    try:
        logger.info(f"Background processing started for {document_id}")
        
        # Initialize processors
        llm_client = LLMClient()
        processor = DocumentProcessor(llm_client)
        
        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found for processing")
            return
        
        # Process document
        results = processor.process_document(
            file_path=file_path,
            document=document,
            db=db
        )
        
        logger.info(f"Background processing completed for {document_id}: {results}")
        
    except Exception as e:
        logger.error(f"Background processing failed for {document_id}: {e}", exc_info=True)
        
        # Update document with error status
        document = db.query(Document).filter(Document.id == document_id).first()
        if document and document.doc_metadata:
            document.doc_metadata["status"] = "failed"
            document.doc_metadata["error"] = str(e)
            db.commit()
    finally:
        db.close()
