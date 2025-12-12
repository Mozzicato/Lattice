"""
OCR Engine for page-level text extraction.
Uses Tesseract when available and returns confidence metadata.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

try:
    import pytesseract
    from pytesseract import Output
except Exception:  # pragma: no cover - optional dependency
    pytesseract = None
    Output = None

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


class OcrEngine:
    """Lightweight OCR wrapper with graceful degradation."""

    def __init__(self, low_confidence_threshold: int = 75):
        self.low_confidence_threshold = low_confidence_threshold
        self.provider = "tesseract" if pytesseract else "unavailable"

    def available(self) -> bool:
        return pytesseract is not None

    def extract_text(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Run OCR on an image. Returns None when OCR is unavailable or fails.
        """
        if not self.available():
            logger.warning("OCR unavailable: pytesseract not installed")
            return None

        try:
            path = Path(image_path)
            if not path.exists():
                logger.warning("OCR skipped: %s does not exist", image_path)
                return None

            image = Image.open(path)
            data = pytesseract.image_to_data(
                image,
                config="--oem 3 --psm 6",
                output_type=Output.DICT,
            )

            words: List[str] = []
            confidences: List[float] = []
            low_conf: List[Dict[str, Any]] = []

            for i, word in enumerate(data.get("text", [])):
                if not word or word.isspace():
                    continue
                conf_raw = data.get("conf", [])[i]
                try:
                    conf_val = float(conf_raw)
                except Exception:
                    conf_val = -1

                words.append(word)
                if conf_val >= 0:
                    confidences.append(conf_val)
                    if conf_val < self.low_confidence_threshold:
                        low_conf.append(
                            {
                                "text": word,
                                "confidence": conf_val,
                                "bbox": self._extract_bbox(data, i),
                            }
                        )

            text = " ".join(words).strip()
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

            result = OcrResult(
                text=text,
                average_confidence=round(avg_conf, 2),
                provider=self.provider,
                low_confidence_segments=low_conf,
            )
            return result.to_dict()
        except Exception as exc:  # pragma: no cover - external dependency
            logger.error("OCR failed for %s: %s", image_path, exc)
            return None

    def _extract_bbox(self, data: Dict[str, List[Any]], index: int) -> Dict[str, Any]:
        return {
            "left": data.get("left", [None])[index],
            "top": data.get("top", [None])[index],
            "width": data.get("width", [None])[index],
            "height": data.get("height", [None])[index],
        }
