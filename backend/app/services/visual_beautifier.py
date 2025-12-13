"""
Visual Note Beautification Service
OCR-based note beautification with proper formula formatting
"""
import logging
import os
import re
import html
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncGenerator
from dataclasses import dataclass

from app.config import settings
from app.services.ocr_engine import OcrEngine
from app.services.equation_extractor import EquationExtractor

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
    Transforms notes into beautiful HTML documents using OCR and formula extraction.
    MVP approach: No LLM quota limits!
    """
    
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
        """Initialize OCR-based beautifier (no LLM required for MVP)"""
        self.ocr_engine = OcrEngine(low_confidence_threshold=75)
        self.equation_extractor = EquationExtractor()
        logger.info("OCR-based Note Beautifier initialized (MVP mode - no quota limits!)")
    
    async def _analyze_page_with_vision(
        self,
        snapshot_path: str,
        page_number: int,
        document_id: str,
        document_metadata: Dict[str, Any],
    ) -> PageAnalysis:
        """Analyze a single page using OCR (no LLM required for MVP)."""

        if not snapshot_path or not Path(snapshot_path).exists():
            return PageAnalysis(
                page_number=page_number,
                snapshot_path="",
                html_content=self._missing_page_block(page_number),
                success=False,
                error="Missing snapshot",
            )

        # Use OCR to extract text
        text_info = self._extract_page_text(document_metadata, page_number, snapshot_path)
        page_images = self._get_page_images(document_metadata, page_number, document_id)
        
        # Render clean HTML with proper formula formatting
        html_content = self._render_page_content(
            page_number=page_number,
            document_id=document_id,
            text_info=text_info,
            images=page_images,
            snapshot_path=snapshot_path,
        )

        return PageAnalysis(
            page_number=page_number,
            snapshot_path=snapshot_path,
            html_content=html_content,
            success=True,
            error=None,
        )

    def _missing_page_block(self, page_number: int) -> str:
        return (
            f'<div class="callout warning"><div class="callout-icon">⚠️'
            f'</div><div class="callout-content">Page {page_number} not found</div></div>'
        )

    def _extract_page_text(
        self,
        document_metadata: Dict[str, Any],
        page_number: int,
        snapshot_path: Optional[str],
    ) -> Dict[str, Any]:
        """Pick the richest text for a page using stored metadata and OCR."""
        page_texts = document_metadata.get("page_texts") or {}
        chosen_text = page_texts.get(page_number, "") or ""

        ocr_result = None
        if snapshot_path and self.ocr_engine.available():
            ocr_result = self.ocr_engine.extract_text(snapshot_path)

        if ocr_result:
            ocr_text = (ocr_result.get("text") or "").strip()
            if len(ocr_text) > len(chosen_text):
                chosen_text = ocr_text

        provider = (ocr_result or {}).get("provider") or ("metadata" if chosen_text else "unavailable")
        avg_conf = (ocr_result or {}).get("average_confidence")
        low_conf = (ocr_result or {}).get("low_confidence_segments") or []

        return {
            "text": chosen_text.strip(),
            "provider": provider,
            "average_confidence": avg_conf,
            "low_confidence_segments": low_conf,
        }

    def _get_page_images(self, document_metadata: Dict[str, Any], page_number: int, document_id: str) -> List[Dict[str, Any]]:
        images = []
        for img in document_metadata.get("images", []) or []:
            page_val = img.get("page") or img.get("page_num") or img.get("page_number")
            if page_val == page_number:
                images.append(self._normalize_image_info(img, document_id, page_number))
        return images

    def _normalize_image_info(self, img: Dict[str, Any], document_id: str, page_number: int) -> Dict[str, Any]:
        path = img.get("path") or ""
        url = self._to_public_url(path, document_id)
        caption = img.get("filename") or img.get("caption") or f"Page {page_number} image"
        return {"url": url or path, "caption": caption}

    def _render_page_content(
        self,
        page_number: int,
        document_id: str,
        text_info: Dict[str, Any],
        images: List[Dict[str, Any]],
        snapshot_path: Optional[str],
    ) -> str:
        snapshot_url = self._to_public_url(snapshot_path, document_id) if snapshot_path else None
        text_html = self._render_text_block(text_info.get("text", ""))
        image_html = self._render_images(images)

        meta_bits = []
        if text_info.get("provider"):
            meta_bits.append(f"Text source: {text_info['provider']}")
        if text_info.get("average_confidence") is not None:
            meta_bits.append(f"Avg OCR confidence: {text_info['average_confidence']}")
        meta_line = " • ".join(meta_bits)

        snapshot_block = (
            f'<div class="page-snapshot"><img src="{snapshot_url}" alt="Page {page_number} snapshot"></div>'
            if snapshot_url
            else ""
        )

        return (
            f'<div class="callout tip"><div class="callout-icon">🧠'
            f'</div><div class="callout-content"><div class="callout-title">Page insights'
            f'</div><p>{meta_line or "OCR disabled or unavailable; showing page assets."}</p>'
            f"</div></div>{text_html}{image_html}{snapshot_block}"
        )

    def _render_images(self, images: List[Dict[str, Any]]) -> str:
        if not images:
            return ""
        cards = []
        for img in images:
            url = img.get("url")
            caption = html.escape(img.get("caption") or "Figure")
            if not url:
                continue
            cards.append(
                f'<div class="image-card"><img src="{url}" alt="{caption}">'  # noqa: E501
                f'<div class="figure-caption">{caption}</div></div>'
            )
        return f"<div class=\"image-grid\">{''.join(cards)}</div>"

    def _render_text_block(self, text: str) -> str:
        if not text or not text.strip():
            return '<p class="text-secondary">No text extracted for this page.</p>'

        blocks = [blk.strip() for blk in text.split("\n\n") if blk.strip()]
        rendered: List[str] = []
        for blk in blocks:
            if self._is_list_block(blk):
                rendered.append(self._format_list_block(blk))
            else:
                eqs = self.equation_extractor.extract_equations(blk)
                processed = self._inject_equations(blk, eqs)
                rendered.append(f"<p>{processed.replace('\n', '<br>')}</p>")

        return "\n".join(rendered)

    def _is_list_block(self, block: str) -> bool:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            return False
        return all(self._is_list_line(line) for line in lines)

    def _is_list_line(self, line: str) -> bool:
        return bool(re.match(r"^([-*•·]|\d+[\.)])\s+", line))

    def _format_list_block(self, block: str) -> str:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        items = []
        for line in lines:
            clean = re.sub(r"^([-*•·]|\d+[\.|\)])\s+", "", line).strip()
            eqs = self.equation_extractor.extract_equations(clean)
            items.append(f"<li>{self._inject_equations(clean, eqs)}</li>")
        return f"<ul>{''.join(items)}</ul>"

    def _inject_equations(self, text: str, equations: List[Any]) -> str:
        if not equations:
            return html.escape(text)

        output: List[str] = []
        cursor = 0
        for eq in equations:
            raw = eq.raw_match
            start = text.find(raw, cursor)
            if start == -1:
                continue
            output.append(html.escape(text[cursor:start]))
            latex = eq.latex
            raw_trim = raw.strip()
            is_block = raw_trim.startswith("$$") or raw_trim.startswith("\\[") or raw_trim.startswith("\\begin")
            if is_block:
                output.append(f'<div class="equation-block">\\[{latex}\\]</div>')
            else:
                output.append(f'<span class="inline-math">\\({latex}\\)</span>')
            cursor = start + len(raw)

        output.append(html.escape(text[cursor:]))
        return "".join(output)

    def _to_public_url(self, path: str, document_id: str) -> Optional[str]:
        if not path:
            return None
        try:
            uploads_root = str(Path(settings.UPLOAD_DIR).resolve())
            resolved = str(Path(path).resolve())
            if resolved.startswith(uploads_root):
                rel = Path(resolved).relative_to(uploads_root)
                return f"/uploads/{rel.as_posix()}"
        except Exception:
            pass

        if os.path.isabs(path):
            return f"/uploads/{document_id}/{Path(path).name}"

        return path
    
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
                analysis = await self._analyze_page_with_vision(snapshot_path, page_num, document_id, document_metadata)
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
                analysis = await self._analyze_page_with_vision(snapshot_path, page_num, document_id, document_metadata)
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

