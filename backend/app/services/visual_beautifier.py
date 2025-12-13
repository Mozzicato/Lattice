from .llm_client import LLMClient
from .ocr_engine import OCREngine

class NoteBeautifier:
    def __init__(self):
        self.llm = LLMClient()
        self.ocr = OCREngine()
        self.system_prompt = """
You are Lattice, a Note Beautifier.
Your goal is to take raw, potentially messy OCR text from handwritten notes and transform it into a CLEAN, BEAUTIFUL, EDUCATIONAL document.

Guidelines:
1.  **Fix Grammar & Spelling:** Correct any errors.
2.  **Format Math:** Convert all mathematical expressions into proper LaTeX format (wrapped in $ or $$).
3.  **Structure:** Organize the content with clear headings and bullet points.
4.  **Clarify:** If a sentence is ambiguous, rewrite it to be clearer while preserving the original meaning.
5.  **Flag Uncertainty:** If a part is unintelligible, mark it with [?] or a note.

Output Format:
Markdown with LaTeX.
"""

    async def beautify_page(self, image_path: str) -> str:
        # 1. Extract raw text via OCR
        raw_text = await self.ocr.extract_text(image_path)
        
        # 2. Send to LLM for reconstruction
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Beautify this raw OCR text:\n\n{raw_text}"}
        ]
        
        beautified_text = await self.llm.get_completion(messages)
        return beautified_text
