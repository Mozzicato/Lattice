"""
OCR Engine for page-level text extraction.
Uses EasyOCR for superior accuracy on academic documents and formulas.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    easyocr = None
    EASYOCR_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    """Structured OCR result."""
    text: str
    average_confidence: float
    provider: str
    low_confidence_segments: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "average_confidence": self.average_confidence,
            "provider": self.provider,
            "low_confidence_segments": self.low_confidence_segments,
        }



# Global cache for EasyOCR reader to avoid reloading models
_reader_cache = None

class OcrEngine:
    """EasyOCR-based text extraction with confidence scoring."""

    def __init__(self, low_confidence_threshold: int = 75):
        global _reader_cache
        self.low_confidence_threshold = low_confidence_threshold
        self.provider = "easyocr" if EASYOCR_AVAILABLE else "unavailable"
        self.reader = None
        
        if EASYOCR_AVAILABLE:
            try:
                # Initialize EasyOCR with English support (add more languages as needed)
                if _reader_cache is None:
                    logger.info("Loading EasyOCR model...")
                    _reader_cache = easyocr.Reader(['en'], gpu=False, verbose=False)
                    logger.info("EasyOCR initialized successfully")
                else:
                    logger.info("Using cached EasyOCR model")
                
                self.reader = _reader_cache
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                self.reader = None
                self.provider = "unavailable"

    def available(self) -> bool:
        return self.reader is not None

    def extract_text(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Run OCR on an image using EasyOCR. Returns None when OCR is unavailable or fails.
        """
        if not self.available():
            logger.warning("OCR unavailable: EasyOCR not initialized")
            return None

        try:
            path = Path(image_path)
            if not path.exists():
                logger.warning("OCR skipped: %s does not exist", image_path)
                return None

            # EasyOCR returns list of ([bbox], text, confidence)
            results = self.reader.readtext(str(path))

            words: List[str] = []
            confidences: List[float] = []
            low_conf: List[Dict[str, Any]] = []

            for bbox, text, conf in results:
                if not text or not text.strip():
                    continue
                
                # Convert confidence from 0-1 to 0-100
                conf_val = conf * 100
                
                words.append(text)
                confidences.append(conf_val)
                
                if conf_val < self.low_confidence_threshold:
                    low_conf.append({
                        "text": text,
                        "confidence": round(conf_val, 2),
                        "bbox": self._format_bbox(bbox),
                    })

            text_output = " ".join(words).strip()
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

            result = OcrResult(
                text=text_output,
                average_confidence=round(avg_conf, 2),
                provider=self.provider,
                low_confidence_segments=low_conf,
            )
            return result.to_dict()
        except Exception as exc:  # pragma: no cover - external dependency
            logger.error("OCR failed for %s: %s", image_path, exc)
            return None

    def _format_bbox(self, bbox: List[List[int]]) -> Dict[str, Any]:
        """Convert EasyOCR bbox format to standardized format."""
        # EasyOCR bbox is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        # Convert to {left, top, width, height}
        xs = [point[0] for point in bbox]
        ys = [point[1] for point in bbox]
        return {
            "left": min(xs),
            "top": min(ys),
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
        }
