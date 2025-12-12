"""
Visual Note Beautification API Endpoint
Generates beautiful HTML/CSS output from page snapshots using Vision AI
Supports streaming to show progress as pages complete
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import logging
import json
from datetime import datetime
from pathlib import Path

from app.database import get_db
from app.models import Document
from app.services.visual_beautifier import VisualBeautifier
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class VisualBeautifyRequest(BaseModel):
    """Request for visual beautification"""
    document_id: str


class VisualBeautifyResponse(BaseModel):
    """Response from visual beautification"""
    document_id: str
    original_filename: str
    status: str
    total_pages: int
    pages_analyzed: int
    successful_analyses: int
    html_preview_url: str
    html_download_url: str
    created_at: datetime
    page_results: list


@router.post("/notes/beautify-visual", response_model=VisualBeautifyResponse)
async def beautify_notes_visual(
    request: VisualBeautifyRequest,
    db: Session = Depends(get_db)
):
    """
    Beautify notes using Visual AI analysis.
    
    This endpoint:
    1. Takes real page snapshots (PNG images)
    2. Uses Gemini Vision to analyze ALL content (text, formulas, diagrams, images)
    3. Generates beautiful HTML/CSS output like a pitch deck generator
    
    Returns URLs for previewing and downloading the beautified HTML document.
    """
    # Get document
    document = db.query(Document).filter(Document.id == request.document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    metadata = document.doc_metadata or {}
    
    # Check if we have page snapshots
    page_count = metadata.get("page_count", 0)
    if page_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no pages. Please wait for processing to complete."
        )
    
    logger.info(f"Starting visual beautification for document {request.document_id}")
    logger.info(f"  Total pages: {page_count}")
    
    # Initialize visual beautifier
    beautifier = VisualBeautifier()
    
    # Perform beautification
    try:
        result = await beautifier.beautify_document(
            document_id=request.document_id,
            document_metadata=metadata,
            document_filename=document.filename
        )
        
        # Update document metadata
        metadata["visual_beautification"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": result["status"],
            "pages_analyzed": result["pages_analyzed"],
            "successful_analyses": result["successful_analyses"]
        }
        document.doc_metadata = metadata
        db.commit()
        
        return VisualBeautifyResponse(
            document_id=request.document_id,
            original_filename=document.filename,
            status=result["status"],
            total_pages=result["total_pages"],
            pages_analyzed=result["pages_analyzed"],
            successful_analyses=result["successful_analyses"],
            html_preview_url=result["preview_url"],
            html_download_url=result["download_url"],
            created_at=datetime.utcnow(),
            page_results=result["page_results"]
        )
        
    except Exception as e:
        logger.error(f"Visual beautification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Beautification failed: {str(e)}"
        )


@router.get("/notes/{document_id}/beautified-visual/preview")
async def preview_beautified_notes(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Preview the beautified HTML document in the browser.
    Returns the full HTML page for rendering.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    html_path = Path(settings.UPLOAD_DIR) / document_id / "beautified.html"
    
    if not html_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beautified document not found. Please run beautification first."
        )
    
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content)


@router.get("/notes/{document_id}/beautified-visual/download")
async def download_beautified_notes(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Download the beautified HTML document as a file.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    html_path = Path(settings.UPLOAD_DIR) / document_id / "beautified.html"
    
    if not html_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beautified document not found. Please run beautification first."
        )
    
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Generate filename
    original_name = Path(document.filename).stem
    download_filename = f"{original_name}_beautified.html"
    
    return HTMLResponse(
        content=html_content,
        headers={
            "Content-Disposition": f'attachment; filename="{download_filename}"'
        }
    )


@router.get("/notes/{document_id}/beautified-visual/status")
async def get_beautification_status(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Check if a document has been visually beautified.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    metadata = document.doc_metadata or {}
    beautification_info = metadata.get("visual_beautification")
    
    html_path = Path(settings.UPLOAD_DIR) / document_id / "beautified.html"
    
    return {
        "document_id": document_id,
        "has_beautification": html_path.exists(),
        "beautification_info": beautification_info,
        "preview_url": f"/api/v1/notes/{document_id}/beautified-visual/preview" if html_path.exists() else None,
        "download_url": f"/api/v1/notes/{document_id}/beautified-visual/download" if html_path.exists() else None
    }


@router.get("/notes/{document_id}/beautify-visual/stream")
async def beautify_notes_visual_stream(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Stream beautification progress using Server-Sent Events.
    
    Events:
    - start: {type: "start", total_pages: N, document_id: "..."}
    - progress: {type: "progress", page: N, total: M, status: "processing"}
    - page_done: {type: "page_done", page: N, total: M, success: bool, html: "..."}
    - complete: {type: "complete", total_pages: N, successful: M, preview_url: "...", download_url: "..."}
    - error: {type: "error", message: "..."}
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    metadata = document.doc_metadata or {}
    page_count = metadata.get("page_count", 0)
    
    if page_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document has no pages")
    
    logger.info(f"Starting streaming beautification for {document_id} ({page_count} pages)")
    
    beautifier = VisualBeautifier()
    
    async def generate():
        try:
            async for event in beautifier.beautify_document_streaming(
                document_id=document_id,
                document_metadata=metadata,
                document_filename=document.filename
            ):
                yield event
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
