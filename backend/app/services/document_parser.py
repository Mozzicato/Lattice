"""
Document parsing utilities for extracting text and images from various file formats
"""
import os
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
from pypdf import PdfReader
from PIL import Image
import io

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    """Represents content extracted from a single page."""
    page_num: int
    text: Optional[str] = None
    images: List[Dict[str, Any]] = None  # List of image metadata
    snapshot_path: Optional[str] = None  # Path to page snapshot

    def __post_init__(self):
        if self.images is None:
            self.images = []


class DocumentParser:
    """
    Parses documents (PDF, images) to extract text and images.
    """

    def __init__(self):
        self.supported_formats = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']

    def render_page_to_image(self, file_path: str, page_num: int = 1, dpi: int = 200) -> Optional[str]:
        """
        Render a PDF page to an image file.
        Returns the path to the saved image.
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            if page_num < 1 or page_num > len(doc):
                logger.error(f"Page {page_num} out of range (1-{len(doc)})")
                return None
                
            page = doc.load_page(page_num - 1)
            pix = page.get_pixmap(dpi=dpi)
            
            # Save to temporary file
            output_dir = Path("extracted_images")
            output_dir.mkdir(exist_ok=True)
            
            image_filename = f"rendered_doc_{Path(file_path).stem}_page_{page_num}.png"
            output_path = output_dir / image_filename
            
            pix.save(str(output_path))
            return str(output_path)
            
        except ImportError:
            logger.error("PyMuPDF (fitz) not installed. Cannot render PDF pages.")
            return None
        except Exception as e:
            logger.error(f"Failed to render page {page_num} of {file_path}: {e}")
            return None

    def get_page_count(self, file_path: str) -> int:
        """
        Get the number of pages in a document.
        For images, returns 1.
        """
        file_ext = Path(file_path).suffix.lower()

        if file_ext == '.pdf':
            try:
                reader = PdfReader(file_path)
                return len(reader.pages)
            except Exception as e:
                logger.error(f"Failed to read PDF {file_path}: {e}")
                return 1
        elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            return 1
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")

    def extract_all_pages(self, file_path: str, document_id: int, save_snapshots: bool = True) -> List[PageContent]:
        """
        Extract content from all pages of a document.

        Args:
            file_path: Path to the document file
            document_id: Database ID of the document
            save_snapshots: Whether to save page snapshots

        Returns:
            List of PageContent objects
        """
        file_ext = Path(file_path).suffix.lower()
        pages = []

        if file_ext == '.pdf':
            try:
                reader = PdfReader(file_path)
                for i, page in enumerate(reader.pages, 1):
                    page_content = PageContent(page_num=i)

                    # Extract text
                    try:
                        text = page.extract_text()
                        page_content.text = text if text.strip() else None
                    except Exception as e:
                        logger.warning(f"Failed to extract text from page {i}: {e}")
                        page_content.text = None

                    # Extract images
                    images = []
                    try:
                        for j, image in enumerate(page.images):
                            # Save image to file
                            image_data = image.data
                            if hasattr(image, 'data') and image.data:
                                image_filename = f"extracted_images/doc_{document_id}_page_{i}_img_{j}.png"
                                os.makedirs(os.path.dirname(image_filename), exist_ok=True)

                                # Convert image data to PIL Image
                                img = Image.open(io.BytesIO(image_data))
                                img.save(image_filename)

                                images.append({
                                    'path': image_filename,
                                    'description': f'Image {j+1} from page {i}'
                                })
                    except Exception as e:
                        logger.warning(f"Failed to extract images from page {i}: {e}")

                    page_content.images = images

                    # Create snapshot (simplified - just use first image or create placeholder)
                    if save_snapshots:
                        snapshot_dir = f"snapshots/doc_{document_id}"
                        os.makedirs(snapshot_dir, exist_ok=True)
                        page_content.snapshot_path = f"{snapshot_dir}/page_{i}.png"

                        # For now, create a placeholder or use extracted image
                        if images:
                            # Copy first image as snapshot
                            import shutil
                            shutil.copy(images[0]['path'], page_content.snapshot_path)
                        else:
                            # Create a simple placeholder image
                            placeholder = Image.new('RGB', (800, 600), color='white')
                            placeholder.save(page_content.snapshot_path)

                    pages.append(page_content)

            except Exception as e:
                logger.error(f"Failed to process PDF {file_path}: {e}")
                # Return single page with error
                pages.append(PageContent(page_num=1, text=f"Error processing PDF: {e}"))

        elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            # Single image file
            page_content = PageContent(page_num=1)
            page_content.text = None  # No direct text, will use OCR
            page_content.images = [{
                'path': file_path,
                'description': 'Main document image'
            }]
            if save_snapshots:
                page_content.snapshot_path = file_path
            pages.append(page_content)

        else:
            raise ValueError(f"Unsupported file format: {file_ext}")

        return pages