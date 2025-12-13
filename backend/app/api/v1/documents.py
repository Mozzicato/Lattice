from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ...database import get_db
from ... import models, schemas
import shutil
import os
from datetime import datetime

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=schemas.Document)
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    try:
        # Generate a safe filename
        # In a real app, we'd want to sanitize this further
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
        await db.refresh(new_doc)
        
        return new_doc
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{document_id}", response_model=schemas.Document)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(models.Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
