"""
Visual Beautifier - Two-Stage LLM Pipeline
Stage 1: Nemotron Vision → raw transcription from page image
Stage 2: Text LLM (Gemini/Groq) → cleanup, formatting, correction
"""
import os
import logging
from pathlib import Path
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class NoteBeautifier:
    """
    Beautifies handwritten notes using a two-stage LLM pipeline.
    Stage 1 (Vision):  PDF/Image → Nemotron → raw transcription
    Stage 2 (Cleanup): raw text → Gemini/Groq → polished Markdown/LaTeX
    """

    def __init__(self):
        self.llm = LLMClient()

        # Stage 1: Vision prompt — just get ALL the text off the page accurately
        self.vision_prompt = r"""You are an OCR transcription engine. Your ONLY job is to transcribe EVERYTHING visible on this page.

RULES:
1. Transcribe ALL text exactly as written - every word, every symbol, every number
2. For mathematical expressions, wrap them in dollar signs: $inline$ or $$block$$  
3. Preserve the order of content as it appears on the page (top to bottom, left to right)
4. If there are numbered questions/problems, keep the numbering
5. If you see diagrams, describe them briefly in brackets: [Diagram: ...]
6. Do NOT skip anything. Do NOT summarize. Transcribe EVERYTHING.
7. Use ## for major section headers you can identify
8. Use - for bullet points if the original has them

Output raw text/markdown. No commentary. Just the transcription."""

        # Stage 2: Cleanup prompt — format and polish the raw transcription
        self.cleanup_prompt = r"""You are Lattice, a professional academic document formatter. You will receive a RAW transcription of handwritten notes (possibly with OCR errors). Your job is to CLEAN IT UP and produce beautiful, well-structured output.

### YOUR TASKS:
1. **Fix OCR errors**: Correct obvious misspellings and garbled text while preserving technical terms
2. **Structure properly**: 
   - Use # for title, ## for sections, ### for subsections
   - Number questions/problems sequentially (1, 2, 3, ...)
   - Use bullet points for lists
3. **Format ALL math properly**:
   - Every math expression MUST be inside delimiters
   - Inline: $x^2 + 3x + 1$
   - Block (standalone equations): $$\int_0^1 f(x)\,dx$$
   - Multi-line derivations in a single block:
     $$
     \begin{aligned}
     f(x) &= x^2 + 1 \\
     f'(x) &= 2x
     \end{aligned}
     $$
4. **Clean up formatting**: Remove artifacts, fix spacing, make it look professional
5. **Preserve ALL content**: Do NOT remove, summarize, or skip any content from the original
6. **If it's an assignment**: Number each question clearly, format sub-parts as (a), (b), (c)

### CRITICAL LATEX RULES:
- NEVER output bare LaTeX commands outside dollar signs
- BAD: \frac{1}{2}     GOOD: $\frac{1}{2}$
- BAD: \nabla^2 f      GOOD: $\nabla^2 f$
- Greek letters in text must use inline math: "the angle $\theta$" NOT "the angle θ"
- For cases/piecewise: wrap in $$\begin{cases}...\end{cases}$$

### OUTPUT FORMAT:
Return ONLY clean Markdown. No ```markdown``` blocks. No explanations about what you changed."""

    async def beautify_page(self, file_path: str, page_number: int = 1) -> str:
        """
        Beautify a single page using the two-stage LLM pipeline.
        
        Stage 1: Vision model transcribes the page image
        Stage 2: Text model cleans up and formats the transcription
        """
        target_image_path = None
        temp_image_created = False

        try:
            file_ext = Path(file_path).suffix.lower()

            # ── Step 1: Get image of the page ──
            if file_ext == '.pdf':
                try:
                    target_image_path = self._render_pdf_page(file_path, page_number)
                    if not target_image_path:
                        return f"[Error: Could not render PDF page {page_number}]"
                    temp_image_created = True
                except Exception as e:
                    return f"[Error: Render Exception for page {page_number}: {str(e)}]"
            elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif']:
                target_image_path = file_path
            else:
                return f"[Error: Unsupported file type: {file_ext}]"

            if not target_image_path or not os.path.exists(target_image_path):
                return "[Error: Image file not found for processing]"

            # ── Stage 1: Vision LLM → Raw Transcription ──
            logger.info(f"[Stage 1] Sending page {page_number} to Nemotron for transcription...")
            
            vision_messages = [
                {"role": "system", "content": self.vision_prompt},
                {
                    "role": "user",
                    "content": f"Transcribe everything on page {page_number} of these notes.",
                    "images": [target_image_path]
                }
            ]

            raw_transcription = await self.llm.get_completion(vision_messages)

            if not raw_transcription or not raw_transcription.strip():
                return "[Error: Vision LLM returned empty response]"
            
            if raw_transcription.startswith("Error:"):
                return f"[Stage 1 Error: {raw_transcription}]"

            logger.info(f"[Stage 1] Got {len(raw_transcription)} chars from Nemotron for page {page_number}")
            logger.debug(f"[Stage 1 Raw Output Preview]: {raw_transcription[:300]}...")

            # ── Stage 2: Text LLM → Cleanup & Formatting ──
            logger.info(f"[Stage 2] Sending raw transcription to text model for cleanup...")

            cleanup_messages = [
                {"role": "system", "content": self.cleanup_prompt},
                {
                    "role": "user",
                    "content": f"Here is the raw transcription of page {page_number}. Clean it up and format it beautifully:\n\n---\n{raw_transcription}\n---"
                }
            ]

            polished_text = await self.llm.text_completion(cleanup_messages, temperature=0.3)

            if not polished_text or not polished_text.strip():
                # If cleanup fails, return the raw transcription (better than nothing)
                logger.warning(f"[Stage 2] Cleanup LLM returned empty — using raw transcription")
                return raw_transcription.strip()

            if polished_text.startswith("Error:"):
                logger.warning(f"[Stage 2] Cleanup failed: {polished_text} — using raw transcription")
                return raw_transcription.strip()

            logger.info(f"[Stage 2] Cleanup produced {len(polished_text)} chars for page {page_number}")
            return polished_text.strip()

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
