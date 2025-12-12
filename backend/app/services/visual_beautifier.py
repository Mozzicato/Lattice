"""
Visual Note Beautification Service
Uses LLM Vision to analyze page snapshots and generate beautiful HTML/CSS output
"""
import logging
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncGenerator
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PageAnalysis:
    """Analysis result for a single page"""
    page_number: int
    snapshot_path: str
    html_content: str
    success: bool
    error: Optional[str] = None


class VisualBeautifier:
    """
    Transforms notes into beautiful HTML documents using Vision AI.
    """
    
    # Rate limiting for Gemini free tier (1.5 Flash allows 15 RPM)
    REQUESTS_PER_MINUTE = 15
    MIN_DELAY_BETWEEN_REQUESTS = 4.0  # 4 seconds is safe for 15 RPM
    MAX_RETRIES = 3
    RETRY_DELAY = 10.0
    
    # Track quota exhaustion across requests
    quota_exhausted = False
    quota_exhausted_time = 0
    
    CSS_TEMPLATE = """
    :root {
        --primary-color: #1e293b;
        --secondary-color: #334155;
        --accent-color: #4f46e5;
        --text-primary: #0f172a;
        --text-secondary: #475569;
        --bg-primary: #ffffff;
        --bg-secondary: #f1f5f9;
        --bg-accent: #eef2ff;
        --border-color: #e2e8f0;
        --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
        --font-mono: 'JetBrains Mono', monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: var(--font-sans);
        font-size: 18px;
        line-height: 1.8;
        color: var(--text-primary);
        background: var(--bg-secondary);
        padding: 2rem;
        -webkit-font-smoothing: antialiased;
    }
    .document-container {
        max-width: 960px;
        margin: 0 auto;
        background: var(--bg-primary);
        border-radius: 24px;
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1);
        overflow: hidden;
    }
    .document-header {
        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
        color: white;
        padding: 4rem 3rem;
        text-align: center;
    }
    .document-title { font-size: 3rem; font-weight: 800; margin-bottom: 1rem; letter-spacing: -0.02em; line-height: 1.2; }
    .document-subtitle { font-size: 1.25rem; opacity: 0.9; font-weight: 500; }
    .document-meta { margin-top: 1.5rem; font-size: 0.95rem; opacity: 0.8; font-family: var(--font-mono); }
    .page-section { padding: 3.5rem; border-bottom: 1px solid var(--border-color); }
    .page-section:last-child { border-bottom: none; }
    .page-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 2rem;
        padding-bottom: 1.5rem;
        border-bottom: 3px solid var(--bg-accent);
    }
    .page-number {
        background: var(--accent-color);
        color: white;
        width: 42px;
        height: 42px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1.1rem;
        box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.3);
    }
    .page-title { font-size: 1.75rem; font-weight: 700; color: var(--primary-color); letter-spacing: -0.01em; }
    h1, h2, h3, h4 { margin-top: 2rem; margin-bottom: 1rem; font-weight: 700; line-height: 1.3; color: var(--primary-color); }
    h1 { font-size: 2.5rem; letter-spacing: -0.02em; }
    h2 { font-size: 2rem; letter-spacing: -0.01em; border-bottom: 2px solid var(--bg-accent); padding-bottom: 0.75rem; }
    h3 { font-size: 1.5rem; color: var(--accent-color); }
    p { margin-bottom: 1.25rem; text-align: justify; }
    strong { font-weight: 700; color: var(--primary-color); }
    ul, ol { margin: 1.5rem 0; padding-left: 1.5rem; }
    li { margin-bottom: 0.75rem; padding-left: 0.5rem; }
    ul li::marker { color: var(--accent-color); }
    .definition {
        background: var(--bg-accent);
        border-left: 6px solid var(--accent-color);
        padding: 1.5rem 2rem;
        margin: 2rem 0;
        border-radius: 0 16px 16px 0;
    }
    .definition-term { font-weight: 800; color: var(--accent-color); margin-bottom: 0.5rem; font-size: 1.1rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .equation-block {
        background: var(--bg-primary);
        border: 2px solid var(--border-color);
        border-radius: 16px;
        padding: 2rem;
        margin: 2rem 0;
        text-align: center;
        overflow-x: auto;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }
    .figure-container { margin: 2.5rem 0; text-align: center; }
    .figure-container img {
        max-width: 100%;
        border-radius: 16px;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
        border: 1px solid var(--border-color);
    }
    .figure-caption { margin-top: 1rem; font-size: 0.95rem; color: var(--text-secondary); font-weight: 500; }
    .table-container { margin: 2rem 0; overflow-x: auto; border-radius: 16px; border: 1px solid var(--border-color); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    table { width: 100%; border-collapse: collapse; }
    th { background: var(--secondary-color); color: white; padding: 1rem 1.5rem; text-align: left; font-weight: 600; }
    td { padding: 1rem 1.5rem; border-bottom: 1px solid var(--border-color); }
    tr:nth-child(even) { background: var(--bg-secondary); }
    code { background: var(--bg-secondary); padding: 0.2rem 0.5rem; border-radius: 6px; font-family: var(--font-mono); color: var(--accent-color); font-weight: 600; }
    .callout { border-radius: 16px; padding: 1.5rem; margin: 2rem 0; display: flex; gap: 1.25rem; align-items: flex-start; }
    .callout-icon { font-size: 1.75rem; line-height: 1; }
    .callout-title { font-weight: 700; margin-bottom: 0.5rem; font-size: 1.1rem; }
    .callout.note { background: #eff6ff; border: 2px solid #bfdbfe; }
    .callout.note .callout-title { color: #1e40af; }
    .callout.warning { background: #fffbeb; border: 2px solid #fde68a; }
    .callout.warning .callout-title { color: #92400e; }
    .callout.tip { background: #ecfdf5; border: 2px solid #a7f3d0; }
    .callout.tip .callout-title { color: #065f46; }
    .key-points {
        background: linear-gradient(135deg, #f8fafc, #f1f5f9);
        border: 2px solid #cbd5e1;
        border-radius: 20px;
        padding: 2rem;
        margin: 2.5rem 0;
    }
    .key-points-title { font-weight: 800; color: var(--secondary-color); margin-bottom: 1rem; font-size: 1.25rem; display: flex; align-items: center; gap: 0.5rem; }
    .document-footer {
        background: var(--bg-secondary);
        padding: 2rem 3rem;
        text-align: center;
        color: var(--text-secondary);
        font-size: 0.9rem;
        border-top: 1px solid var(--border-color);
        font-weight: 500;
    }
    @media print {
        body { background: white; padding: 0; }
        .document-container { box-shadow: none; max-width: 100%; border-radius: 0; }
        .page-section { page-break-inside: avoid; padding: 2rem; }
    }
    @media (max-width: 768px) {
        body { padding: 1rem; }
        .document-header { padding: 2.5rem 1.5rem; }
        .document-title { font-size: 2rem; }
        .page-section { padding: 1.5rem; }
    }
    """
    
    def __init__(self):
        self.gemini_client = None
        self.groq_client = None
        self.last_request_time = 0
        self._init_clients()
    
    def _init_clients(self):
        # 1. Try Groq (First Choice)
        try:
            import os
            from groq import Groq
            groq_api_key = os.getenv("GROQ_API_KEY")
            if groq_api_key:
                self.groq_client = Groq(api_key=groq_api_key)
                logger.info("Groq Vision client initialized (Llama 3.2 Vision)")
            else:
                logger.warning("No GROQ_API_KEY found")
        except Exception as e:
            logger.warning(f"Failed to initialize Groq: {e}")

        # 2. Initialize Gemini (Fallback)
        try:
            import google.generativeai as genai
            api_key = settings.GEMINI_API_KEY
            if api_key:
                genai.configure(api_key=api_key)
                # User requested gemini-2.5-flash-lite as fallback
                self.gemini_client = genai.GenerativeModel('gemini-2.5-flash-lite')
                logger.info("Gemini Vision client initialized (gemini-2.5-flash-lite)")
            else:
                logger.warning("No Gemini API key - using fallback mode")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            # Fallback to 1.5 Flash if 2.5 fails
            try:
                import google.generativeai as genai
                self.gemini_client = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("Fallback: Gemini Vision client initialized (gemini-1.5-flash)")
            except:
                pass
    
    async def _wait_for_rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.MIN_DELAY_BETWEEN_REQUESTS:
            wait_time = self.MIN_DELAY_BETWEEN_REQUESTS - elapsed
            logger.info(f"Rate limit: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        self.last_request_time = time.time()
    
    async def _analyze_page_with_vision(self, snapshot_path: str, page_number: int, document_id: str) -> PageAnalysis:
        # Check if quota was recently exhausted - skip API calls entirely
        if VisualBeautifier.quota_exhausted:
            time_since_exhaustion = time.time() - VisualBeautifier.quota_exhausted_time
            if time_since_exhaustion < 60:  # Wait at least 60 seconds before retrying
                logger.info(f"Page {page_number}: Skipping API call (quota exhausted {time_since_exhaustion:.0f}s ago)")
                return self._fallback_analysis(snapshot_path, page_number, document_id, "Quota exhausted - using original image")
            else:
                VisualBeautifier.quota_exhausted = False  # Reset after cooldown
        
        # Priority 1: Groq
        if self.groq_client:
            try:
                return await self._analyze_with_groq(snapshot_path, page_number, document_id)
            except Exception as e:
                logger.error(f"Groq analysis failed for page {page_number}: {e}")
                # Fall through to Gemini
        
        # Priority 2: Gemini
        if self.gemini_client:
            return await self._analyze_with_gemini(snapshot_path, page_number, document_id)
            
        return self._fallback_analysis(snapshot_path, page_number, document_id)

    async def _analyze_with_groq(self, snapshot_path: str, page_number: int, document_id: str) -> PageAnalysis:
        for attempt in range(self.MAX_RETRIES):
            try:
                import base64
                
                # Encode image
                with open(snapshot_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
                prompt = """Analyze this page and generate semantic HTML to recreate its content beautifully.
EXTRACT EVERYTHING: text, headings, formulas, diagrams, tables, lists.
OUTPUT ONLY HTML (no markdown, no code blocks). Just the content HTML."""

                completion = await asyncio.to_thread(
                    self.groq_client.chat.completions.create,
                    model="llama-3.2-11b-vision-preview",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{encoded_string}"
                                    }
                                }
                            ]
                        }
                    ],
                    temperature=0.1,
                    max_tokens=4096,
                    top_p=1,
                    stream=False,
                    stop=None,
                )
                
                html = completion.choices[0].message.content
                if html.startswith("```"):
                    lines = html.split("\n")
                    html = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                html = html.replace("```html", "").replace("```", "").strip()
                
                return PageAnalysis(page_number=page_number, snapshot_path=snapshot_path, html_content=html, success=True)

            except Exception as e:
                logger.warning(f"Groq Page {page_number} attempt {attempt+1} failed: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                    continue
                
                # If Groq fails completely, try Gemini as fallback
                if self.gemini_client:
                    logger.info(f"Groq failed for page {page_number}, falling back to Gemini...")
                    return await self._analyze_with_gemini(snapshot_path, page_number, document_id)
                    
                return self._fallback_analysis(snapshot_path, page_number, document_id, str(e))

    async def _analyze_with_gemini(self, snapshot_path: str, page_number: int, document_id: str) -> PageAnalysis:
        for attempt in range(self.MAX_RETRIES):
            try:
                import PIL.Image
                await self._wait_for_rate_limit()
                
                img = PIL.Image.open(snapshot_path)
                
                prompt = """Analyze this page and generate semantic HTML to recreate its content beautifully.

EXTRACT EVERYTHING: text, headings, formulas, diagrams, tables, lists.

CRITICAL FORMATTING INSTRUCTIONS:
- Use <h2> for main sections, <h3> for subsections.
- Use <strong> for bold text (ensure key terms are bold).
- Use <div class="equation-block">\\[LaTeX\\]</div> for display equations.
- Use <span class="inline-math">\\(LaTeX\\)</span> for inline math.
- Use <div class="definition"><div class="definition-term">Term</div><div class="definition-content">Def</div></div> for definitions.
- Use <div class="callout note"><div class="callout-icon">💡</div><div class="callout-content"><div class="callout-title">Note</div>...</div></div> for important notes.
- Use <div class="figure-container"><p><strong>Figure:</strong> Description</p></div> for images/diagrams.
- Use <div class="key-points"><div class="key-points-title">Key Points</div><ul>...</ul></div> for summaries.
- Use <div class="table-container"><table>...</table></div> for tables.

OUTPUT ONLY HTML (no markdown, no code blocks). Just the content HTML."""

                response = await asyncio.to_thread(
                    self.gemini_client.generate_content, [prompt, img]
                )
                
                if response and response.text:
                    html = response.text.strip()
                    if html.startswith("```"):
                        lines = html.split("\n")
                        html = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                    html = html.replace("```html", "").replace("```", "").strip()
                    
                    return PageAnalysis(page_number=page_number, snapshot_path=snapshot_path, html_content=html, success=True)
                    
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Page {page_number} attempt {attempt+1} failed: {error_msg}")
                
                if "429" in error_msg or "quota" in error_msg.lower():
                    # Mark quota as exhausted to skip remaining pages
                    VisualBeautifier.quota_exhausted = True
                    VisualBeautifier.quota_exhausted_time = time.time()
                    logger.warning("Quota exhausted - falling back to original images for remaining pages")
                    return self._fallback_analysis(snapshot_path, page_number, document_id, "API quota limit reached")
                
                # For other errors, retry once then fallback
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                    continue
                
                return self._fallback_analysis(snapshot_path, page_number, document_id, error_msg)
        
        return self._fallback_analysis(snapshot_path, page_number, document_id, "Max retries exceeded")
    
    def _fallback_analysis(self, snapshot_path: str, page_number: int, document_id: str, error: Optional[str] = None) -> PageAnalysis:
        snapshot_url = f"/uploads/{document_id}/pages/page_{page_number:04d}.png"
        html = f"""
        <div class="callout note">
            <div class="callout-icon">📄</div>
            <div class="callout-content">
                <div class="callout-title">Original Page</div>
                <p>AI formatting unavailable. Showing original snapshot.</p>
            </div>
        </div>
        <div class="figure-container">
            <img src="{snapshot_url}" alt="Page {page_number}">
            <div class="figure-caption"><strong>Page {page_number}</strong></div>
        </div>
        """
        return PageAnalysis(page_number=page_number, snapshot_path=snapshot_path, html_content=html, success=False, error=error)
    
    async def beautify_document_streaming(self, document_id: str, document_metadata: Dict[str, Any], document_filename: str) -> AsyncGenerator[str, None]:
        """Stream beautification results as Server-Sent Events"""
        import json
        
        total_pages = document_metadata.get("page_count", 1)
        page_snapshots = document_metadata.get("page_snapshots", [])
        
        # Send start event immediately
        yield f"data: {json.dumps({'type': 'start', 'total_pages': total_pages, 'document_id': document_id, 'css': self.CSS_TEMPLATE})}\n\n"
        
        # Force flush by yielding a small comment
        yield ": ping\n\n"
        
        page_analyses: List[PageAnalysis] = []
        successful = 0
        
        for page_num in range(1, total_pages + 1):
            snapshot_path = None
            for snap in page_snapshots:
                if snap.get("page") == page_num:
                    snapshot_path = snap.get("path")
                    break
            
            if not snapshot_path:
                snapshot_path = f"{settings.UPLOAD_DIR}/{document_id}/pages/page_{page_num:04d}.png"
                if not Path(snapshot_path).exists():
                    snapshot_path = None
            
            # Send progress update BEFORE processing
            yield f"data: {json.dumps({'type': 'progress', 'page': page_num, 'total': total_pages, 'status': 'processing'})}\n\n"
            yield ": ping\n\n"
            
            if snapshot_path:
                analysis = await self._analyze_page_with_vision(snapshot_path, page_num, document_id)
            else:
                analysis = PageAnalysis(page_number=page_num, snapshot_path="", html_content=f'<div class="callout warning"><div class="callout-icon">⚠️</div><div class="callout-content">Page {page_num} not found</div></div>', success=False, error="Missing snapshot")
            
            page_analyses.append(analysis)
            if analysis.success:
                successful += 1
            
            # Send page done event IMMEDIATELY after processing
            yield f"data: {json.dumps({'type': 'page_done', 'page': page_num, 'total': total_pages, 'success': analysis.success, 'html': analysis.html_content})}\n\n"
            yield ": ping\n\n"
        
        # Generate final HTML
        html_doc = self._generate_html_document(document_filename, document_id, page_analyses, document_metadata)
        html_path = Path(settings.UPLOAD_DIR) / document_id / "beautified.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_doc)
        
        yield f"data: {json.dumps({'type': 'complete', 'total_pages': total_pages, 'successful': successful, 'preview_url': f'/api/v1/notes/{document_id}/beautified-visual/preview', 'download_url': f'/api/v1/notes/{document_id}/beautified-visual/download'})}\n\n"
    
    async def beautify_document(self, document_id: str, document_metadata: Dict[str, Any], document_filename: str) -> Dict[str, Any]:
        """Non-streaming version"""
        total_pages = document_metadata.get("page_count", 1)
        page_snapshots = document_metadata.get("page_snapshots", [])
        
        page_analyses = []
        successful = 0
        
        for page_num in range(1, total_pages + 1):
            snapshot_path = None
            for snap in page_snapshots:
                if snap.get("page") == page_num:
                    snapshot_path = snap.get("path")
                    break
            
            if not snapshot_path:
                snapshot_path = f"{settings.UPLOAD_DIR}/{document_id}/pages/page_{page_num:04d}.png"
                if not Path(snapshot_path).exists():
                    snapshot_path = None
            
            if snapshot_path:
                analysis = await self._analyze_page_with_vision(snapshot_path, page_num, document_id)
            else:
                analysis = PageAnalysis(page_number=page_num, snapshot_path="", html_content=f'<div class="callout warning">Page {page_num} not found</div>', success=False)
            
            page_analyses.append(analysis)
            if analysis.success:
                successful += 1
        
        html_doc = self._generate_html_document(document_filename, document_id, page_analyses, document_metadata)
        html_path = Path(settings.UPLOAD_DIR) / document_id / "beautified.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_doc)
        
        return {
            "status": "success",
            "document_id": document_id,
            "total_pages": total_pages,
            "pages_analyzed": len(page_analyses),
            "successful_analyses": successful,
            "preview_url": f"/api/v1/notes/{document_id}/beautified-visual/preview",
            "download_url": f"/api/v1/notes/{document_id}/beautified-visual/download",
            "page_results": [{"page": a.page_number, "success": a.success, "error": a.error} for a in page_analyses]
        }
    
    def _generate_html_document(self, filename: str, document_id: str, page_analyses: List[PageAnalysis], metadata: Dict[str, Any]) -> str:
        pages_html = "\n".join([
            f'''<section class="page-section" id="page-{a.page_number}">
                <div class="page-header">
                    <span class="page-number">{a.page_number}</span>
                    <h2 class="page-title">Page {a.page_number}</h2>
                </div>
                <div class="page-content">{a.html_content}</div>
            </section>'''
            for a in page_analyses
        ])
        
        doc_title = Path(filename).stem.replace("_", " ").replace("-", " ").title()
        toc = "\n".join([f'<li><a href="#page-{i+1}">Page {i+1}</a></li>' for i in range(len(page_analyses))])
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{doc_title} - Beautified Notes</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>{self.CSS_TEMPLATE}</style>
</head>
<body>
    <div class="document-container">
        <header class="document-header">
            <h1 class="document-title">📚 {doc_title}</h1>
            <p class="document-subtitle">Beautified Study Notes</p>
            <div class="document-meta">{len(page_analyses)} pages • Lattice AI</div>
        </header>
        <nav class="page-section" style="background: var(--bg-accent);">
            <h3 style="margin-top: 0;">📑 Contents</h3>
            <ol style="columns: 2;">{toc}</ol>
        </nav>
        <main>{pages_html}</main>
        <footer class="document-footer">✨ Beautified with Lattice AI • {filename}</footer>
    </div>
    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            renderMathInElement(document.body, {{
                delimiters: [
                    {{left: '$$', right: '$$', display: true}},
                    {{left: '$', right: '$', display: false}},
                    {{left: '\\\\[', right: '\\\\]', display: true}},
                    {{left: '\\\\(', right: '\\\\)', display: false}}
                ],
                throwOnError: false
            }});
        }});
    </script>
</body>
</html>"""
