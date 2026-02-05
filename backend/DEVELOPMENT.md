Quick setup notes for improved OCR/math extraction

- Install system Tesseract (Windows): https://github.com/tesseract-ocr/tesseract
  - Set OCR_TESSERACT_CMD in `.env` if Tesseract is not on PATH.

- Optional Mathpix integration:
  - Set `ENABLE_MATHPIX=true` and `MATHPIX_APP_ID` and `MATHPIX_APP_KEY` in `.env` to enable image→LaTeX conversion.

- Python deps: run `python -m pip install -r requirements.txt`

- Frontend: from `frontend/` run `npm install` to add KaTeX and `react-katex`.

- Tests: from `backend/` run `pytest -q` (OCR tests will be skipped if Tesseract not available).