"""
Note Rewriter API Endpoint
Converts poorly formatted notes into beautiful, well-structured documents
Processes ALL pages and includes image references
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
import logging
from pydantic import BaseModel

from app.database import get_db
from app.models import Document
from app.services.llm_client import LLMClient

router = APIRouter()
logger = logging.getLogger(__name__)


class NoteRewriteRequest(BaseModel):
    """Request to rewrite notes"""
    document_id: str
    focus_areas: Optional[list[str]] = None


class NoteRewriteResponse(BaseModel):
    """Rewritten note response"""
    title: str
    formatted_content: str
    sections: list[dict]
    page_count: int
    image_count: int
    download_url: str


@router.post("/notes/rewrite", response_model=NoteRewriteResponse)
async def rewrite_notes(
    request: NoteRewriteRequest,
    db: Session = Depends(get_db)
):
    """
    Take poorly formatted notes and rewrite them beautifully
    Processes ALL pages with image references
    
    Features:
    - Processes EVERY page of the document
    - Includes references to images on each page
    - Corrects handwriting transcription errors
    - Improves formatting and structure
    - Adds clear section headings
    - Organizes equations properly
    - Creates professional document
    """
    # Get document
    document = db.query(Document).filter(Document.id == request.document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Initialize LLM
    llm_client = LLMClient()
    
    # Get metadata
    metadata = document.doc_metadata or {}
    page_count = metadata.get('page_count', 1)
    images = metadata.get('images', [])
    concepts = metadata.get('concepts', [])
    page_texts = metadata.get('page_texts', {})
    
    logger.info(f"Rewriting notes for document {request.document_id}")
    logger.info(f"  Total pages: {page_count}")
    logger.info(f"  Total images: {len(images)}")
    
    # Process ALL pages - build comprehensive content
    all_formatted_parts = []
    
    # Process in chunks of 3-4 pages to avoid token limits
    pages_per_chunk = 3
    total_chunks = (page_count + pages_per_chunk - 1) // pages_per_chunk
    
    for chunk_idx in range(total_chunks):
        start_page = chunk_idx * pages_per_chunk + 1
        end_page = min((chunk_idx + 1) * pages_per_chunk, page_count)
        
        logger.info(f"  Processing pages {start_page} to {end_page}...")
        
        # Collect text and images for this chunk
        chunk_content = []
        chunk_images = []
        
        for page_num in range(start_page, end_page + 1):
            page_text = page_texts.get(str(page_num), page_texts.get(page_num, ""))
            if page_text:
                chunk_content.append(f"--- PAGE {page_num} ---\n{page_text}")
            
            # Find images on this page
            page_images = [img for img in images if img.get('page') == page_num]
            if page_images:
                chunk_images.extend(page_images)
        
        if not chunk_content:
            continue
        
        # Build prompt for this chunk
        image_info = ""
        if chunk_images:
            image_info = f"\n\nImages on these pages ({len(chunk_images)} images):\n"
            for img in chunk_images:
                image_info += f"- Page {img.get('page')}: Image {img.get('index', 0)+1} (size: {img.get('width', 0):.0f}x{img.get('height', 0):.0f})\n"
        
        prompt = f"""You are an expert academic note-taker. Rewrite these student notes into a beautiful, well-structured document.

This is pages {start_page} to {end_page} of a {page_count}-page document.

ORIGINAL NOTES:
{chr(10).join(chunk_content)}
{image_info}

Instructions:
1. **Preserve ALL content** - Do not skip or summarize. Include everything from every page.
2. **Correct errors** - Fix spelling, grammar, transcription errors
3. **Improve structure** - Add clear headings and subheadings
4. **Format equations** - Present equations with $$ for display math and $ for inline
5. **Reference images** - Where there's an image, write [See Image on Page X] or describe what the image likely shows
6. **Enhance readability** - Use bullet points, numbered lists, proper paragraphs
7. **Maintain accuracy** - Keep all technical content accurate

Output clean, well-formatted markdown. Start immediately with the content:"""

        try:
            chunk_formatted = llm_client.complete(
                prompt,
                temperature=0.3,
                max_tokens=4000
            )
            
            if chunk_formatted and chunk_formatted.strip():
                all_formatted_parts.append(chunk_formatted)
                logger.info(f"    Chunk {chunk_idx + 1}/{total_chunks}: Generated {len(chunk_formatted)} chars")
            else:
                logger.warning(f"    Chunk {chunk_idx + 1}: Empty response, using original text")
                all_formatted_parts.append("\n".join(chunk_content))
                
        except Exception as e:
            logger.error(f"    Chunk {chunk_idx + 1} failed: {e}")
            # Fallback to original text
            all_formatted_parts.append("\n".join(chunk_content))
    
    if not all_formatted_parts:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process any pages. Please try again."
        )
    
    # Combine all parts
    formatted_content = "\n\n---\n\n".join(all_formatted_parts)
    
    # Add header with document info
    header = f"""# Formatted Notes

**Original Document:** {document.filename}
**Total Pages:** {page_count}
**Images:** {len(images)}
**Generated by:** Lattice AI

---

"""
    formatted_content = header + formatted_content
    
    # Extract title
    title = f"Formatted Notes - {document.filename}"
    
    # Parse sections
    sections = []
    current_section = None
    lines = formatted_content.split('\n')
    
    for line in lines:
        if line.startswith('## '):
            if current_section:
                sections.append(current_section)
            current_section = {
                'title': line.replace('## ', '').strip(),
                'content': []
            }
        elif current_section and line.strip():
            current_section['content'].append(line)
    
    if current_section:
        sections.append(current_section)
    
    # Store rewritten content
    if not metadata.get('rewritten_notes'):
        metadata['rewritten_notes'] = []
    
    metadata['rewritten_notes'].append({
        'title': title,
        'content': formatted_content,
        'page_count': page_count,
        'image_count': len(images),
        'timestamp': 'now'
    })
    
    document.doc_metadata = metadata
    db.commit()
    
    logger.info(f"Successfully rewrote notes: {len(formatted_content)} chars, {len(sections)} sections")
    
    return NoteRewriteResponse(
        title=title,
        formatted_content=formatted_content,
        sections=sections,
        page_count=page_count,
        image_count=len(images),
        download_url=f"/api/v1/notes/{request.document_id}/download"
    )


@router.get("/notes/{document_id}/latest")
async def get_latest_rewritten_notes(
    document_id: str,
    db: Session = Depends(get_db)
):
    """Get the latest rewritten notes for a document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    metadata = document.doc_metadata or {}
    rewritten_notes = metadata.get('rewritten_notes', [])
    
    if not rewritten_notes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No rewritten notes found"
        )
    
    return rewritten_notes[-1]


@router.get("/notes/{document_id}/download")
async def download_formatted_notes(
    document_id: str,
    db: Session = Depends(get_db)
):
    """Download formatted notes as Markdown file"""
    from fastapi.responses import Response
    
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    metadata = document.doc_metadata or {}
    rewritten_notes = metadata.get('rewritten_notes', [])
    
    if not rewritten_notes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No rewritten notes found"
        )
    
    latest_note = rewritten_notes[-1]
    content = latest_note['content']
    filename = f"{latest_note['title'].replace(' ', '_')}.md"
    
    return Response(
        content=content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
