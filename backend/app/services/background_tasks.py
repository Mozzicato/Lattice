import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app import models

logger = logging.getLogger(__name__)


async def run_beautify_job(document_id: int, job_id: int | None = None):
    """Background job to run beautification and persist results.

    Now supports multi-page processing via visual pipeline.
    """
    from datetime import datetime
    from sqlalchemy.future import select
    from sqlalchemy.orm import selectinload
    from app.services.visual_beautifier import NoteBeautifier
    from app.services.document_parser import DocumentParser
    from app.models import Job, Document, Page
    from pathlib import Path

    beautifier = NoteBeautifier()
    parser = DocumentParser()

    async with AsyncSessionLocal() as session:  # type: AsyncSession
        # Eager load document with pages
        query = select(Document).where(Document.id == document_id).options(selectinload(Document.pages))
        result = await session.execute(query)
        doc = result.scalar_one_or_none()
        
        job = await session.get(Job, job_id) if job_id else None
        if job:
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.progress = 5
            job.message = "Starting beautification"
            session.add(job)
            await session.commit()

        if not doc:
            logger.error(f"Beautify job: document {document_id} not found")
            if job:
                job.status = "error"
                job.message = "Document not found"
                job.progress = 0
                session.add(job)
                await session.commit()
            return

        try:
            # Determine page count
            page_count = 1
            if doc.file_path.lower().endswith('.pdf'):
                try:
                    page_count = parser.get_page_count(doc.file_path)
                except Exception:
                    page_count = 1
            
            logger.info(f"Processing {page_count} pages for document {document_id}")

            for i in range(1, page_count + 1):
                current_progress = 10 + int((i / page_count) * 80)
                if job:
                    job.progress = current_progress
                    job.message = f"Processing page {i} of {page_count}..."
                    session.add(job)
                    await session.commit()

                # Run Visual Beautification for this page
                # We ignore existing text/OCR to ensure we use the vision model
                beautified_text = await beautifier.beautify_page(doc.file_path, page_number=i)

                # Check if page exists in DB, else create
                # We can't rely on existing doc.pages index because DB order might not match or pages might be missing
                # So we search or filter
                existing_page = next((p for p in doc.pages if p.page_number == i), None)
                
                if not existing_page:
                    new_page = Page(
                        document_id=doc.id, 
                        page_number=i, 
                        image_path=doc.file_path, 
                        beautified_text=beautified_text
                    )
                    session.add(new_page)
                else:
                    existing_page.beautified_text = beautified_text
                    session.add(existing_page)

            doc.status = "beautified"
            session.add(doc)
            await session.commit()

            if job:
                job.progress = 100
                job.status = "completed"
                job.message = "Beautification complete"
                job.finished_at = datetime.utcnow()
                session.add(job)
                await session.commit()

            logger.info(f"Beautify job complete for document {document_id}")

        except Exception as e:
            logger.exception(f"Beautify job failed for document {document_id}: {e}")
            doc.status = "error"
            session.add(doc)
            if job:
                job.status = "error"
                job.message = str(e)
                job.progress = 0
                job.finished_at = datetime.utcnow()
                session.add(job)
            await session.commit()
