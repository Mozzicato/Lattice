# Quick Start: Note Beautification Feature

## Installation

### 1. Install System Dependencies
```bash
# For OCR support (Ubuntu/Debian)
sudo apt-get install -y tesseract-ocr

# For macOS
brew install tesseract
```

### 2. Update Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

The following has been added to `requirements.txt`:
- `pytesseract==0.3.10` - Python wrapper for Tesseract OCR

### 3. Configuration
Ensure your `.env` file includes:
```
OCR_LOW_CONFIDENCE=75
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=your_api_key_here
```

## Quick Test

### 1. Start the Backend
```bash
cd backend
python -m uvicorn main:app --reload
```

API will be available at: `http://localhost:8000/api/docs`

### 2. Start the Frontend
```bash
cd frontend
npm start
```

Frontend will be available at: `http://localhost:3000`

### 3. Test the Beautification Flow

#### Upload a Document
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@sample.pdf"
```

#### Get Document Status
```bash
curl http://localhost:8000/api/v1/documents/{document_id}
```

Wait for `doc_metadata.status` to be `"ready_for_learning"`

#### Beautify Notes
```bash
curl -X POST http://localhost:8000/api/v1/notes/beautify \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "{document_id}",
    "target_language_level": "undergraduate",
    "include_image_references": true
  }'
```

#### Download Beautified Notes
```bash
curl -o beautified.md \
  http://localhost:8000/api/v1/notes/{document_id}/beautified/download
```

## Frontend Usage

### In the UI
1. **Upload**: Drag & drop or click to upload a document
2. **Wait**: Processing indicator shows extraction progress
3. **Explore**: Chat with AI or explore document structure
4. **Beautify**: Click "✨ Beautify My Notes" in the sidebar
5. **Review**: See beautified content with:
   - Pages processed / total
   - Formula count
   - Quality warnings (if any)
6. **Download**: Click "⬇️ Download" to save as Markdown

## API Endpoints Reference

### Core Beautification
```
POST   /api/v1/notes/beautify
GET    /api/v1/notes/{document_id}/beautified/download
```

### Related Endpoints
```
POST   /api/v1/documents/upload
GET    /api/v1/documents/{document_id}
GET    /api/v1/documents/{document_id}/equations
```

## What Each Component Does

### OCR Engine
- Extracts text from page snapshots
- Tracks confidence for each word
- Identifies low-confidence segments
- File: `backend/app/services/ocr_engine.py`

### Note Beautifier
- Performs page-by-page refinement
- Enhances formatting and language
- Counts formulas and warnings
- Generates document intro/conclusion
- File: `backend/app/services/note_beautifier.py`

### Document Parser
- Saves page snapshots (200 DPI)
- Extracts images and text from all pages
- Stores snapshots at: `uploads/{doc_id}/pages/`
- File: `backend/app/services/document_parser.py`

### Document Processor
- Coordinates full document processing
- Runs OCR on all pages
- Stores results in metadata
- File: `backend/app/services/document_processor.py`

## Troubleshooting

### OCR Not Working
**Error:** `pytesseract.TesseractNotFoundError`

**Solution:** Install Tesseract
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows: Download installer from https://github.com/UB-Mannheim/tesseract/wiki
```

### LLM Errors
**Error:** "LLM client not available"

**Solution:** Check Gemini API key in `.env`
```bash
# Verify API key works
curl https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY
```

### Out of Memory
If beautifying large documents, the system chunks by 3-4 pages automatically.

**Adjust in** `app/services/note_beautifier.py`:
```python
pages_per_chunk = 2  # Smaller chunks for memory-constrained systems
```

### Pages Missing from Output
The system guarantees complete page coverage. Check:
- `pages_processed` in response should equal `total_pages`
- `pages_with_warnings` should list any problematic pages
- Review `low_confidence_summary` for OCR issues

## Performance Notes

### Expected Processing Times (per page)
- OCR: 1-3 seconds
- LLM beautification: 3-5 seconds  
- **Total: 4-8 seconds per page**

### For a 100-page Document
- Processing time: ~10 minutes
- Disk usage: ~150 MB (snapshots + metadata)
- Memory peak: ~500 MB

### Optimization Tips
1. **Parallel OCR**: Modify to process pages in parallel (future enhancement)
2. **Batching**: Group pages more aggressively if needed
3. **LLM Caching**: Cache beautification prompts for similar page types

## Example Output

### Input (Raw Notes)
```
Ch 3 - Electromagnetism
3.1 Electric Fields
Electric field is the force per unit charge
E = F/q where F is force, q is charge
Units: newtons per coulomb (N/C)
[diagram showing field lines]
```

### Output (Beautified)
```markdown
## Chapter 3: Electromagnetism

### 3.1 Electric Fields

The **electric field** is defined as the electric force per unit charge. 
It represents the effect of one charge on another in space.

**Definition:**
$$E = \frac{F}{q}$$

Where:
- $E$ is the electric field strength
- $F$ is the electric force (in newtons)
- $q$ is the test charge (in coulombs)

**Units:** Newtons per coulomb (N/C) or volts per meter (V/m)

[See Image on Page 3]

**Key Insight:** The electric field is a vector quantity that depends only on 
the source charge, not on the test charge used to measure it.
```

## Next Steps

1. **Deploy**: Use Docker Compose for production
   ```bash
   docker-compose up
   ```

2. **Monitor**: Add logging to track beautification metrics
   ```python
   logger.info(f"Beautified {pages_processed} pages in {elapsed_time:.1f}s")
   ```

3. **Extend**: Add custom beautification prompts per document type

4. **Integrate**: Connect to external services (spell check, plagiarism detection)

## Support

For issues or questions:
1. Check logs: `docker logs lattice-backend`
2. Review API docs: `http://localhost:8000/api/docs`
3. Check Gemini API status: `https://status.cloud.google.com`
