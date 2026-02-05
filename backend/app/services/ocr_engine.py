"""
OCR Engine - Simplified Placeholder
Deprecated in favor of Visual LLM pipeline.
Kept minimal structure to prevent API breakage.
"""
import logging
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

class OcrEngine:
    """
    Simplified OCR engine.
    Since we moved to Visual LLM, this engine returns basic messages or empty results
    to satisfy existing API contracts without complex dependencies.
    """

    def __init__(self, low_confidence_threshold: float = 60.0):
        self.low_confidence_threshold = low_confidence_threshold
        self.tesseract_available = False
        logger.info("OcrEngine initialized in legacy mode (No local OCR).")

    def extract_text(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Mock extraction/Basic check. 
        Returns placeholder text as we rely on Vision LLM for actual transcription.
        """
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None

        return {
            'text': "[Legacy OCR: Switch to Beautify for full AI Transcription]",
            'confidence': 100.0,
            'low_confidence_segments': [],
            'total_words': 0,
            'low_confidence_word_count': 0
        }

    def extract_text_with_preprocessing(self, image_path: str) -> Optional[Dict[str, Any]]:
        return self.extract_text(image_path)

