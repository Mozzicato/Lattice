from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from ...database import get_db
from ... import models, schemas
import shutil
import os
from datetime import datetime

from app.services.visual_beautifier import NoteBeautifier

router = APIRouter()
beautifier = NoteBeautifier()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=schemas.Document)
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    try:
        # Generate a safe filename
        file_location = f"{UPLOAD_DIR}/{int(datetime.now().timestamp())}_{file.filename}"
        
        # Save the file
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
            
        # Create DB record
        new_doc = models.Document(
            filename=file.filename,
            file_path=file_location,
            status="uploaded"
        )
        db.add(new_doc)
        await db.commit()
        
        # Re-fetch with eager load to satisfy Pydantic schema
        query = select(models.Document).where(models.Document.id == new_doc.id).options(selectinload(models.Document.pages))
        result = await db.execute(query)
        new_doc = result.scalar_one()
        
        return new_doc
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{document_id}", response_model=schemas.Document)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    query = select(models.Document).where(models.Document.id == document_id).options(selectinload(models.Document.pages))
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.post("/{document_id}/beautify", response_model=schemas.Document)
async def beautify_document(document_id: int, db: AsyncSession = Depends(get_db)):
    # Eager load pages to avoid MissingGreenlet error
    query = select(models.Document).where(models.Document.id == document_id).options(selectinload(models.Document.pages))
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # In a real app, we would iterate over pages. 
    # For MVP, we assume the document file_path points to a single image or we process the file itself.
    
    # 1. Process
    # We'll assume the file_path is an image for this mock
    beautified_content = await beautifier.beautify_page(doc.file_path)
    
    # 2. Save result
    # Check if pages exist
    if not doc.pages:
        new_page = models.Page(
            document_id=doc.id,
            page_number=1,
            image_path=doc.file_path,
            beautified_text=beautified_content
        )
        db.add(new_page)
        # We need to commit to get the ID and relationship update
        await db.commit()
        # Refresh the doc to get the new page in the relationship
        await db.refresh(doc)
        # Re-fetch with eager load because refresh might not load relationships depending on config
        query = select(models.Document).where(models.Document.id == document_id).options(selectinload(models.Document.pages))
        result = await db.execute(query)
        doc = result.scalar_one()
    else:
        # Update existing page (mock logic)
        page = doc.pages[0]
        page.beautified_text = beautified_content
        db.add(page)
        await db.commit()
        await db.refresh(doc)
    
    doc.status = "beautified"
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    
    return doc
