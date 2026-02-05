"""
Visual Beautifier - Vision LLM Pipeline
Takes page screenshots and sends directly to LLM for transcription + beautification.
"""
import os
import logging
from pathlib import Path
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class NoteBeautifier:
    """
    Beautifies handwritten notes using a Vision LLM.
    Pipeline: PDF/Image -> Page Screenshot -> Vision LLM -> Markdown/LaTeX
    """

    def __init__(self):
        self.llm = LLMClient()
        self.system_prompt = """You are Lattice, an expert Mathematical & Academic Document Beautifier.
Your task is to transcribe and beautify handwritten notes into professional Markdown with perfect LaTeX formatting.

### INPUT:
You will receive an IMAGE of a handwritten page containing notes, equations, and diagrams.

### CRITICAL LATEX RULES (MUST FOLLOW):
1. **EVERY mathematical expression MUST be wrapped in dollar signs**:
   - Inline math: `$x^2$`, `$\\alpha$`, `$\\frac{a}{b}$`
   - Block/display math: `$$\\int_0^1 f(x) dx$$`
2. **NEVER output raw LaTeX without delimiters**. BAD: `\\frac{1}{2}`. GOOD: `$\\frac{1}{2}$`
3. **For multi-line equations**, use a SINGLE `$$...$$` block:
   ```
   $$
   \\begin{aligned}
   x &= r\\cos\\theta \\\\
   y &= r\\sin\\theta
   \\end{aligned}
   $$
   ```
4. **For systems/cases**, wrap in `$$...$$`:
   ```
   $$
   \\begin{cases}
   x = r\\cos\\theta \\\\
   y = r\\sin\\theta
   \\end{cases}
   $$
   ```
5. **Greek letters in text** must use inline math: "The angle $\\theta$" NOT "The angle θ"

### OUTPUT REQUIREMENTS:
1. **Transcription & Improvement**: 
   - Transcribe ALL handwritten text accurately and completely.
   - Refine for clarity and professionalism.
   - Do NOT skip or truncate any content.
2. **Mathematical Precision**: 
   - Convert ALL equations to properly-delimited LaTeX.
   - Use `$$...$$` for standalone equations (on their own line).
   - Use `$...$` for inline math within sentences.
3. **Structuring**:
   - Use Markdown headers (#, ##, ###) to organize topics.
   - Use bullet points for lists.
4. **Visual Elements**:
   - Describe diagrams in blockquotes: `> [Diagram: ...]`

### FORMAT:
Return ONLY raw Markdown. No ```markdown``` blocks. Transcribe EVERYTHING on the page."""

    async def beautify_page(self, file_path: str, page_number: int = 1) -> str:
        """
        Beautify a single page using Visual LLM.
        
        Args:
            file_path: Path to the PDF or image file.
            page_number: Page number to process (1-indexed).
        
        Returns:
            Beautified Markdown/LaTeX content.
        """
        target_image_path = None
        temp_image_created = False

        try:
            file_ext = Path(file_path).suffix.lower()

            # Step 1: Get image of the page
            if file_ext == '.pdf':
                # Render PDF page to image
                try:
                    target_image_path = self._render_pdf_page(file_path, page_number)
                    if not target_image_path:
                        try:
                           import fitz
                           diag = "fitz installed"
                        except ImportError:
                           diag = "fitz MISSING"
                        
                        return f"[Error: Could not render PDF page {page_number}. Diag: {diag}]"
                    temp_image_created = True
                except Exception as e:
                    return f"[Error: Render Exception for page {page_number}: {str(e)}]"
            
            elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif']:
                target_image_path = file_path
            else:
                return f"[Error: Unsupported file type: {file_ext}]"

            if not target_image_path or not os.path.exists(target_image_path):
                return "[Error: Image file not found for processing]"

            logger.info(f"Processing page {page_number} from: {target_image_path}")

            # Step 2: Send image to Vision LLM
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": f"Please transcribe and beautify page {page_number} of these handwritten notes.",
                    "images": [target_image_path]
                }
            ]

            beautified_text = await self.llm.get_completion(messages)

            if not beautified_text or not beautified_text.strip():
                return "[Error: LLM returned empty response]"

            return beautified_text.strip()

        except Exception as e:
            logger.exception(f"Error beautifying page {page_number}: {e}")
            return f"[Error during beautification: {str(e)}]"

        finally:
            # Clean up temporary image
            if temp_image_created and target_image_path and os.path.exists(target_image_path):
                try:
                    os.remove(target_image_path)
                except Exception:
                    pass

    def _render_pdf_page(self, pdf_path: str, page_num: int) -> str | None:
        """
        Render a specific PDF page to a PNG image using PyMuPDF.
        """
        try:
            import fitz  # PyMuPDF
            
            abs_path = os.path.abspath(pdf_path)
            if not os.path.exists(abs_path):
                logger.error(f"PDF file does not exist at: {abs_path}")
                raise FileNotFoundError(f"{abs_path} not found")

            doc = fitz.open(abs_path)
            
            if page_num < 1 or page_num > len(doc):
                logger.error(f"Page {page_num} out of range (1-{len(doc)})")
                doc.close()
                return None

            page = doc.load_page(page_num - 1)  # 0-indexed
            
            # Render at 2x resolution for better quality
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)

            # Save to temp file
            output_dir = Path("extracted_images").absolute() # Use absolute path
            output_dir.mkdir(exist_ok=True)
            
            output_path = output_dir / f"page_{page_num}_{os.getpid()}_{os.path.basename(pdf_path)}.png"
            pix.save(str(output_path))

            doc.close()
            logger.info(f"Rendered PDF page {page_num} to {output_path}")
            return str(output_path)

        except ImportError:
            logger.error("PyMuPDF (fitz) is not installed. Run: pip install pymupdf")
            raise
        except Exception as e:
            logger.exception(f"Failed to render PDF page {page_num} of {pdf_path}: {e}")
            raise
