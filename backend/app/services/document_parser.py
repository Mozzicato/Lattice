"""
Document Parser Service
Comprehensive page-by-page parsing with image extraction
"""
import pdfplumber
from pathlib import Path
from typing import Dict, Any, List
import logging
import os
import uuid
from PIL import Image
import io

from app.config import settings

logger = logging.getLogger(__name__)


class PageContent:
    """Represents content from a single page"""
    def __init__(self, page_num: int):
        self.page_num = page_num
        self.text = ""
        self.images: List[Dict[str, Any]] = []
        self.tables: List[Any] = []
        self.snapshot_path: str | None = None


class DocumentParser:
    """
    Parses uploaded documents and extracts structured content.
    Processes ALL pages and extracts ALL images.
    """
    
    def __init__(self):
        self.max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        self.allowed_extensions = settings.ALLOWED_EXTENSIONS
    
    def validate_file(self, file) -> Dict[str, Any]:
        """
        Validate uploaded file
        
        Args:
            file: UploadFile object
            
        Returns:
            Dict with 'valid' boolean and optional 'error' message
        """
        # Check file size
        if hasattr(file, 'size') and file.size > self.max_size_bytes:
            return {
                "valid": False,
                "error": f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB"
            }
        
        # Check extension
        ext = Path(file.filename).suffix.lower()
        if ext not in self.allowed_extensions:
            return {
                "valid": False,
                "error": f"Invalid file type. Allowed types: {', '.join(self.allowed_extensions)}"
            }
        
        return {"valid": True}
    
    def get_page_count(self, file_path: str) -> int:
        """Get total number of pages in PDF"""
        path = Path(file_path)
        if path.suffix.lower() != '.pdf':
            return 1
        
        try:
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except Exception as e:
            logger.error(f"Error getting page count: {e}")
            return 0
    
    def extract_all_pages(self, file_path: str, document_id: str, save_snapshots: bool = True) -> List[PageContent]:
        """
        Extract ALL content from ALL pages including images
        
        Args:
            file_path: Path to the file
            document_id: Document ID for saving images
            save_snapshots: Whether to store full-page snapshots for OCR/preview
            
        Returns:
            List of PageContent objects for each page
        """
        path = Path(file_path)
        
        if path.suffix.lower() == '.pdf':
            return self._extract_all_pdf_pages(file_path, document_id, save_snapshots)
        elif path.suffix.lower() == '.txt':
            # Text files have one "page"
            content = PageContent(1)
            content.text = self._extract_from_text(file_path)
            return [content]
        elif path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.tiff'}:
            return self._extract_from_image(file_path, document_id, save_snapshots)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")
    
    def _extract_all_pdf_pages(self, file_path: str, document_id: str, save_snapshots: bool = True) -> List[PageContent]:
        """Extract ALL content from ALL PDF pages"""
        pages_content: List[PageContent] = []
        
        # Create images directory
        base_dir = Path(settings.UPLOAD_DIR) / document_id
        images_dir = base_dir / "images"
        pages_dir = base_dir / "pages"
        images_dir.mkdir(parents=True, exist_ok=True)
        if save_snapshots:
            pages_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"Processing PDF with {total_pages} pages")
                
                for page_num, page in enumerate(pdf.pages, start=1):
                    logger.info(f"Processing page {page_num}/{total_pages}")
                    
                    page_content = PageContent(page_num)
                    
                    # Save full-page snapshot for OCR/preview
                    if save_snapshots:
                        page_content.snapshot_path = self._save_page_snapshot(page, page_num, pages_dir)
                    
                    # Extract text
                    text = page.extract_text()
                    if text:
                        page_content.text = text
                        logger.info(f"  Page {page_num}: Extracted {len(text)} characters")
                    else:
                        page_content.text = ""
                        logger.warning(f"  Page {page_num}: No text found")
                    
                    # Extract images
                    try:
                        images = page.images
                        if images:
                            logger.info(f"  Page {page_num}: Found {len(images)} images")
                            
                            for img_idx, img in enumerate(images):
                                try:
                                    # Get image data
                                    image_info = self._extract_image(
                                        page, img, page_num, img_idx, images_dir
                                    )
                                    if image_info:
                                        page_content.images.append(image_info)
                                except Exception as e:
                                    logger.warning(f"  Failed to extract image {img_idx} on page {page_num}: {e}")
                    except Exception as e:
                        logger.warning(f"  Page {page_num}: Error extracting images: {e}")
                    
                    # Extract tables
                    try:
                        tables = page.extract_tables()
                        if tables:
                            page_content.tables = tables
                            logger.info(f"  Page {page_num}: Found {len(tables)} tables")
                    except Exception as e:
                        logger.warning(f"  Page {page_num}: Error extracting tables: {e}")
                    
                    pages_content.append(page_content)
                
                logger.info(f"Completed processing all {total_pages} pages")
                
        except Exception as e:
            logger.error(f"Error extracting PDF pages: {e}", exc_info=True)
            raise
        
        return pages_content

    def _extract_from_image(self, file_path: str, document_id: str, save_snapshots: bool = True) -> List[PageContent]:
        """Treat a single image as a one-page document"""
        pages_dir = Path(settings.UPLOAD_DIR) / document_id / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        page_content = PageContent(1)
        if save_snapshots:
            target_path = pages_dir / f"page_0001{Path(file_path).suffix.lower()}"
            try:
                # Copy image so downstream services have a stable path
                Image.open(file_path).save(target_path)
                page_content.snapshot_path = str(target_path)
            except Exception as e:
                logger.warning(f"Failed to persist image snapshot: {e}")
                page_content.snapshot_path = file_path
        else:
            page_content.snapshot_path = file_path

        return [page_content]

    def _save_page_snapshot(self, page, page_num: int, pages_dir: Path) -> str | None:
        """Persist a full-page snapshot for OCR and traceability"""
        try:
            page_image = page.to_image(resolution=200)
            snapshot_path = pages_dir / f"page_{page_num:04d}.png"
            if hasattr(page_image, 'original'):
                page_image.original.save(str(snapshot_path), 'PNG')
            else:
                page_image.save(str(snapshot_path))
            return str(snapshot_path)
        except Exception as e:
            logger.warning(f"Could not save page snapshot {page_num}: {e}")
            return None
    
    def _extract_image(
        self, 
        page, 
        img: Dict, 
        page_num: int, 
        img_idx: int, 
        images_dir: Path
    ) -> Dict[str, Any]:
        """Extract a single image from a PDF page"""
        try:
            # Get image bbox
            x0, y0, x1, y1 = img['x0'], img['top'], img['x1'], img['bottom']
            
            # Crop the image region from page
            cropped = page.within_bbox((x0, y0, x1, y1))
            
            # Get the page image
            page_image = page.to_image(resolution=150)
            
            # Crop to image bounds
            bbox = (
                int(x0 * 150 / 72),  # Convert PDF points to pixels
                int(y0 * 150 / 72),
                int(x1 * 150 / 72),
                int(y1 * 150 / 72)
            )
            
            # Generate filename
            filename = f"page{page_num}_img{img_idx}_{uuid.uuid4().hex[:8]}.png"
            filepath = images_dir / filename
            
            # Try to extract via the image object
            if hasattr(page_image, 'original'):
                pil_image = page_image.original.crop(bbox)
                pil_image.save(str(filepath), 'PNG')
            else:
                # Alternative: save the whole cropped region
                page_image.save(str(filepath))
            
            return {
                "page": page_num,
                "index": img_idx,
                "filename": filename,
                "path": str(filepath),
                "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                "width": x1 - x0,
                "height": y1 - y0
            }
            
        except Exception as e:
            logger.warning(f"Failed to save image: {e}")
            # Still record image metadata even if we couldn't save it
            return {
                "page": page_num,
                "index": img_idx,
                "error": str(e),
                "bbox": {"x0": img.get('x0', 0), "y0": img.get('top', 0), 
                         "x1": img.get('x1', 0), "y1": img.get('bottom', 0)}
            }
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from PDF or text file (legacy method)
        
        Args:
            file_path: Path to the file
            
        Returns:
            Extracted text content
        """
        path = Path(file_path)
        
        if path.suffix.lower() == '.pdf':
            return self._extract_from_pdf(file_path)
        elif path.suffix.lower() == '.txt':
            return self._extract_from_text(file_path)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")
    
    def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF using pdfplumber"""
        try:
            text_content = []
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    if text:
                        # Add page marker
                        text_content.append(f"\n--- PAGE {page_num} ---\n")
                        text_content.append(text)
            
            return "\n".join(text_content)
            
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            raise
    
    def _extract_from_text(self, file_path: str) -> str:
        """Extract text from plain text file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading text file: {e}")
            raise
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract document metadata
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with metadata
        """
        path = Path(file_path)
        metadata = {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "extension": path.suffix
        }
        
        if path.suffix.lower() == '.pdf':
            try:
                with pdfplumber.open(file_path) as pdf:
                    metadata["page_count"] = len(pdf.pages)
                    if pdf.metadata:
                        metadata.update({
                            "title": pdf.metadata.get("Title"),
                            "author": pdf.metadata.get("Author"),
                            "creator": pdf.metadata.get("Creator"),
                        })
            except Exception as e:
                logger.warning(f"Could not extract PDF metadata: {e}")
        
        return metadata
