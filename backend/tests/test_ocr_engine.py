import pytest
from PIL import Image, ImageDraw, ImageFont
import os

from app.services.ocr_engine import OcrEngine


def create_test_image(text: str, path: str):
    img = Image.new('RGB', (400, 100), color='white')
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    d.text((10, 10), text, fill='black', font=font)
    img.save(path)


@pytest.mark.skipif(not OcrEngine().tesseract_available, reason="Tesseract not available on system")
def test_ocr_basic(tmp_path):
    img_path = os.path.join(tmp_path, 'test_text.png')
    create_test_image('F = -kx', img_path)

    ocr = OcrEngine()
    result = ocr.extract_text(img_path)

    assert result is not None
    assert 'F' in result['text'] or 'kx' in result['text']
