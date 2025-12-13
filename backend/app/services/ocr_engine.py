class OCREngine:
    def __init__(self):
        pass

    async def extract_text(self, image_path: str) -> str:
        """
        Mock OCR extraction.
        In production, this would use EasyOCR, Tesseract, or a cloud API (Google Vision, AWS Textract).
        """
        # Simulate extracting text from a handwritten note
        return """
        The harmonic oscilator is a system where the restoring force is proportional to displacement.
        F = -kx
        mx'' + kx = 0
        The solution is x(t) = A cos(wt + phi)
        where w = sqrt(k/m)
        """
