"""
Document API endpoints for upload, processing, and beautification.
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from ...database import get_db
from ... import models, schemas
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()

# Ensure upload directory exists
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload", response_model=schemas.Document)
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload a document (PDF or image) for processing."""
    try:
        # Validate file type
        allowed_types = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}
        file_ext = Path(file.filename or "file").suffix.lower()
        
        if file_ext not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_types)}"
            )
        
        # Generate safe filename
        timestamp = int(datetime.now().timestamp() * 1000)
        safe_filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in (file.filename or "file"))
        file_location = UPLOAD_DIR / f"{timestamp}_{safe_filename}"
        
        # Read and save file
        file_contents = await file.read()
        
        if len(file_contents) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        with open(file_location, "wb") as f:
            f.write(file_contents)
        
        logger.info(f"Saved uploaded file to {file_location} ({len(file_contents)} bytes)")
        
        # Create DB record
        new_doc = models.Document(
            filename=file.filename,
            file_path=str(file_location),
            status="uploaded"
        )
        db.add(new_doc)
        await db.commit()
        
        # Re-fetch with eager load
        query = select(models.Document).where(models.Document.id == new_doc.id).options(selectinload(models.Document.pages))
        result = await db.execute(query)
        new_doc = result.scalar_one()
        
        return new_doc
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/{document_id}", response_model=schemas.Document)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """Get document details by ID."""
    query = select(models.Document).where(models.Document.id == document_id).options(selectinload(models.Document.pages))
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/{document_id}/beautify", response_model=schemas.Document)
async def beautify_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """Run full beautification pipeline on a document (background job)."""
    from app.services.visual_beautifier import NoteBeautifier
    
    beautifier = NoteBeautifier()
    
    # Eager load pages
    query = select(models.Document).where(models.Document.id == document_id).options(selectinload(models.Document.pages))
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check file exists
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail=f"Document file not found: {doc.file_path}")
    
    try:
        # Create a Job record so client can poll progress
        from app.models import Job
        from app.services.background_tasks import run_beautify_job
        import asyncio

        doc.status = "processing"
        db.add(doc)
        await db.commit()

        job = Job(document_id=document_id, status="queued", progress=0, message="Queued")
        db.add(job)
        await db.commit()

        # Try to enqueue to Redis RQ if configured, otherwise schedule in-process
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis  # type: ignore[import-not-found]
                from rq import Queue  # type: ignore[import-not-found]
                conn = redis.from_url(redis_url)
                q = Queue("default", connection=conn)
                q.enqueue("app.services.background_tasks.run_beautify_job", document_id, job.id)
                logger.info(f"Enqueued beautify job {job.id} to Redis queue")
            except ImportError:
                logger.warning("Redis/RQ not installed, running in-process")
                loop = asyncio.get_event_loop()
                loop.create_task(run_beautify_job(document_id, job.id))
            except Exception as e:
                logger.warning(f"Failed to enqueue to Redis, running in-process: {e}")
                loop = asyncio.get_event_loop()
                loop.create_task(run_beautify_job(document_id, job.id))
        else:
            loop = asyncio.get_event_loop()
            loop.create_task(run_beautify_job(document_id, job.id))

        # Return current document state immediately and include job id header
        # Re-fetch with job_id attached for client reference
        query = select(models.Document).where(models.Document.id == document_id).options(selectinload(models.Document.pages))
        result = await db.execute(query)
        doc = result.scalar_one()
        
        # Attach job_id to response for polling
        return JSONResponse(
            content={
                "id": doc.id,
                "filename": doc.filename,
                "file_path": doc.file_path,
                "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
                "status": doc.status,
                "pages": [{"id": p.id, "page_number": p.page_number, "ocr_text": p.ocr_text, "beautified_text": p.beautified_text} for p in doc.pages],
                "job_id": job.id
            },
            headers={"X-Beautify-Job": str(job.id)}
        )

    except Exception as e:
        logger.exception(f"Beautification scheduling failed: {e}")
        raise HTTPException(status_code=500, detail=f"Beautification scheduling failed: {str(e)}")


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get job status for real-time progress updates."""
    from app.models import Job
    query = select(Job).where(Job.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "document_id": job.document_id
    }


@router.post("/{document_id}/process")
async def process_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """Run OCR and equation extraction on a document."""
    from app.services.ocr_engine import OcrEngine
    from app.services.equation_extractor import EquationExtractor
    
    ocr = OcrEngine()
    extractor = EquationExtractor()
    
    query = select(models.Document).where(models.Document.id == document_id).options(selectinload(models.Document.pages))
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail=f"Document file not found: {doc.file_path}")
    
    try:
        # Run OCR
        ocr_result = ocr.extract_text(doc.file_path)
        raw_text = ocr_result.get("text", "") if ocr_result else ""
        
        # Extract equations
        equations = extractor.extract_equations(raw_text)
        latex_content = "\n".join(equations) if equations else None
        
        # Create or update page
        if not doc.pages:
            new_page = models.Page(
                document_id=doc.id,
                page_number=1,
                image_path=doc.file_path,
                ocr_text=raw_text,
                latex_content=latex_content
            )
            db.add(new_page)
        else:
            page = doc.pages[0]
            page.ocr_text = raw_text
            page.latex_content = latex_content
            db.add(page)
        
        doc.status = "processed"
        db.add(doc)
        await db.commit()
        
        return {
            "status": "success",
            "ocr_text": raw_text[:500] + "..." if len(raw_text) > 500 else raw_text,
            "equations_found": len(equations),
            "latex_content": latex_content
        }
        
    except Exception as e:
        logger.exception(f"Processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/{document_id}/pages/{page_id}/update", response_model=schemas.Page)
async def update_page(document_id: int, page_id: int, payload: dict, db: AsyncSession = Depends(get_db)):
    """Update page content (OCR text, LaTeX, beautified text)."""
    query = select(models.Page).where(
        models.Page.id == page_id, 
        models.Page.document_id == document_id
    )
    result = await db.execute(query)
    page = result.scalar_one_or_none()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Update allowed fields
    allowed_fields = {"ocr_text", "latex_content", "beautified_text"}
    for field in allowed_fields:
        if field in payload:
            setattr(page, field, payload[field])
    
    db.add(page)
    await db.commit()
    await db.refresh(page)
    
    return page


@router.get("/{document_id}/download-pdf")
async def download_beautified_pdf(document_id: int, db: AsyncSession = Depends(get_db)):
    """Generate and download beautified PDF for the document."""
    from fastapi.responses import FileResponse
    from app.services.pdf_generator import PDFGenerator
    import tempfile
    
    # Get document with pages
    query = select(models.Document).where(models.Document.id == document_id).options(selectinload(models.Document.pages))
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.pages:
        raise HTTPException(status_code=400, detail="Document has no pages with beautified content")
    
    # Check if any page has beautified text
    beautified_pages = [p for p in doc.pages if p.beautified_text and p.beautified_text.strip()]
    if not beautified_pages:
        raise HTTPException(status_code=400, detail="No beautified content available. Please run beautification first.")
    
    try:
        # Generate PDF
        pdf_gen = PDFGenerator()
        
        # Create temporary file for PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        
        # Extract beautified text from pages
        pages_text = [p.beautified_text for p in beautified_pages if p.beautified_text]
        
        # Generate multi-page PDF
        success = pdf_gen.generate_pdf_from_pages(
            pages_text, 
            tmp_path, 
            title=f"Beautified Notes - {doc.filename}"
        )
        
        if not success:
            raise Exception("PDF generation failed")
        
        # Return PDF file
        return FileResponse(
            tmp_path,
            media_type="application/pdf",
            filename=f"beautified_{Path(doc.filename).stem}.pdf"
        )
        
    except Exception as e:
        logger.exception(f"PDF download failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
