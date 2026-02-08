import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app import models

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
CONCURRENT_PAGES = 2  # Process 2 pages at a time for speed


async def _beautify_single_page(beautifier, file_path: str, page_number: int) -> str:
    """Beautify one page with automatic retry on failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await beautifier.beautify_page(file_path, page_number=page_number)
            # Check if the result is an error
            if result and result.startswith("[Error"):
                if attempt < MAX_RETRIES:
                    logger.warning(f"Page {page_number} attempt {attempt} failed: {result}. Retrying...")
                    await asyncio.sleep(1.5 * attempt)  # Backoff
                    continue
                else:
                    logger.error(f"Page {page_number} failed after {MAX_RETRIES} attempts: {result}")
                    return result
            return result
        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning(f"Page {page_number} attempt {attempt} exception: {e}. Retrying...")
                await asyncio.sleep(1.5 * attempt)
            else:
                logger.error(f"Page {page_number} failed after {MAX_RETRIES} attempts: {e}")
                return f"[Error: Failed after {MAX_RETRIES} retries: {str(e)}]"
    return "[Error: Unexpected retry loop exit]"


async def run_beautify_job(document_id: int, job_id: int | None = None):
    """Background job to run beautification and persist results.

    Now supports multi-page processing via visual pipeline.
    Streams progress updates in real-time via Server-Sent Events.
    """
    from datetime import datetime
    from sqlalchemy.future import select
    from sqlalchemy.orm import selectinload
    from app.services.visual_beautifier import NoteBeautifier
    from app.services.document_parser import DocumentParser
    from app.models import Job, Document, Page
    from app.services.event_stream import event_manager
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
            
            # Publish start event
            if job_id:
                await event_manager.publish_event(job_id, "start", {
                    "message": "Starting beautification",
                    "progress": 5
                })

        if not doc:
            logger.error(f"Beautify job: document {document_id} not found")
            if job:
                job.status = "error"
                job.message = "Document not found"
                job.progress = 0
                session.add(job)
                await session.commit()
                
                # Publish error event
                if job_id:
                    await event_manager.publish_event(job_id, "error", {
                        "message": "Document not found"
                    })
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

            # Process pages in concurrent batches for speed
            page_results = {}  # page_number -> beautified_text

            for batch_start in range(1, page_count + 1, CONCURRENT_PAGES):
                batch_end = min(batch_start + CONCURRENT_PAGES, page_count + 1)
                batch_pages = list(range(batch_start, batch_end))
                batch_label = ", ".join(str(p) for p in batch_pages)

                current_progress = 10 + int((batch_start / page_count) * 80)
                page_msg = f"Processing page(s) {batch_label} of {page_count}..."

                if job:
                    job.progress = current_progress
                    job.message = page_msg
                    session.add(job)
                    await session.commit()

                logger.info(f"Document {document_id}: {page_msg}")

                if job_id:
                    await event_manager.publish_event(job_id, "progress", {
                        "message": page_msg,
                        "progress": current_progress,
                        "page": batch_start,
                        "total_pages": page_count
                    })

                # Launch pages in this batch concurrently
                tasks = [
                    _beautify_single_page(beautifier, doc.file_path, pg)
                    for pg in batch_pages
                ]
                results = await asyncio.gather(*tasks)

                for pg, text in zip(batch_pages, results):
                    page_results[pg] = text
                    logger.info(f"Document {document_id}: Page {pg} -> {len(text)} chars")

            # Persist all results
            for i in range(1, page_count + 1):
                beautified_text = page_results.get(i, "[Error: page not processed]")

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
                
                # Publish completion event
                if job_id:
                    await event_manager.publish_event(job_id, "complete", {
                        "message": "Beautification complete",
                        "progress": 100
                    })

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
                
                # Publish error event
                if job_id:
                    await event_manager.publish_event(job_id, "error", {
                        "message": str(e)
                    })
            else:
                await session.commit()

