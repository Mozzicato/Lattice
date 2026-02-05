"""
PDF Generator Service
Converts beautified markdown text to a professional PDF for download.
Supports Markdown headers, lists, and LaTeX block equations (rendered via matplotlib).
"""
from pathlib import Path
from typing import Optional, List, Tuple
import logging
import io
import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.colors import HexColor
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

import html

class PDFGenerator:
    """Generates PDF from beautified markdown text with proper formatting."""

    def __init__(self):
        """Initialize PDF generator."""
        self.SimpleDocTemplate = SimpleDocTemplate
        self.Paragraph = Paragraph
        self.Spacer = Spacer
        self.PageBreak = PageBreak
        self.Image = Image
        self.letter = letter
        self.getSampleStyleSheet = getSampleStyleSheet
        self.ParagraphStyle = ParagraphStyle
        self.inch = inch
        self.TA_LEFT = TA_LEFT
        self.TA_CENTER = TA_CENTER
        self.TA_JUSTIFY = TA_JUSTIFY
        self.HexColor = HexColor
        
        # We stick to standard fonts but implement strict scrubbing for unsupported chars
        # ReportLab standard fonts (Helvetica) support Latin-1 (mostly). 
        # Unicode chars (like alpha, beta) OUTSIDE of LaTeX images will crash or show garbage.
        # Strategy: The beautifier prompt enforces LaTeX for all math symbols.
        # Here we just scrub anything residual.

    def render_equation(self, latex_text: str, dpi: int = 300, fontsize: int = 20, is_inline: bool = False) -> Optional[io.BytesIO]:
        """
        Render a LaTeX equation to a BytesIO image buffer using Matplotlib.
        """
        try:
            # Strip delimiters
            clean_latex = latex_text.strip()
            if clean_latex.startswith('$$') and clean_latex.endswith('$$'):
                 clean_latex = clean_latex[2:-2]
            elif clean_latex.startswith('$') and clean_latex.endswith('$'):
                 clean_latex = clean_latex[1:-1]
            
            if not clean_latex:
                return None
            
            # Create figure
            # Dynamic size based on content length estimate (rough)
            # For inline, we want minimal height. For block, we allow more.
            
            # Matplotlib configuration for transparent background
            plt.rcParams['text.usetex'] = False # We rely on built-in mathtext which is safer than external latex install
            plt.rcParams['mathtext.fontset'] = 'cm' # Computer Modern

            if is_inline:
                fig = plt.figure(figsize=(0.1, 0.1), dpi=dpi) # Start small, bbox_inches='tight' will expand
                render_str = r"$" + clean_latex + r"$"
                text_elem = fig.text(0, 0, render_str, fontsize=fontsize, va='bottom', ha='left')
            else:
                fig = plt.figure(figsize=(6, 1), dpi=dpi) # Wider canvas for blocks
                render_str = r"$\displaystyle " + clean_latex + r"$"
                text_elem = fig.text(0.5, 0.5, render_str, fontsize=fontsize, ha='center', va='center')
            
            # Save to buffer with tight block
            buf = io.BytesIO()
            # bbox_inches='tight' is crucial - it trims the image to the text exact size
            fig.savefig(buf, format='png', dpi=dpi, transparent=True, bbox_inches='tight', pad_inches=0.02)
            buf.seek(0)
            plt.close(fig)
            return buf
        except Exception as e:
            logger.warning(f"Failed to render equation '{latex_text}': {e}")
            plt.close('all')
            return None

    def _scrub_text(self, text: str) -> str:
        """
        Replace unsupported Unicode characters with ASCII equivalents or HTML entities.
        ReportLab's Helvetica doesn't support Greek/Math chars directly.
        """
        replacements = {
            '–': '-', '—': '-', '“': '"', '”': '"', '‘': "'", '’': "'",
            '…': '...', '•': '*', '→': '->', '←': '<-', '≥': '>=', '≤': '<=',
            '≈': '~', '≠': '!=', '±': '+/-', '×': 'x'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Remove any other non-latin-1 characters that might cause issues
        # Or encode/decode to strip them
        try:
            text.encode('latin-1')
        except UnicodeEncodeError:
            # If it fails, filter out bad chars
            text = ''.join(c for c in text if ord(c) < 256)
            
        return text

    def _parse_markdown(self, text: str) -> List[Tuple[str, str]]:
        lines = text.split('\n')
        elements = []
        
        in_code_block = False
        in_math_block = False  # Explicit $$...$$ block
        in_raw_latex_block = False # Implicit \begin{...} block
        math_buffer = []
        
        for line in lines:
            stripped = line.strip()
            
            # --- Handle Explicit $$ Math Blocks ---
            if stripped == '$$':
                if in_math_block:
                    full_math = '$$' + ' '.join(math_buffer) + '$$'
                    elements.append((full_math, 'equation'))
                    in_math_block = False
                    math_buffer = []
                else:
                    in_math_block = True
                    math_buffer = []
                continue
            
            if stripped.startswith('$$') and not stripped.endswith('$$'):
                in_math_block = True
                math_buffer = [stripped[2:]]
                continue
            
            if in_math_block:
                if stripped.endswith('$$'):
                    math_buffer.append(stripped[:-2])
                    full_math = '$$' + ' '.join(math_buffer) + '$$'
                    elements.append((full_math, 'equation'))
                    in_math_block = False
                    math_buffer = []
                else:
                    math_buffer.append(stripped)
                continue

            if not stripped:
                elements.append(('spacer', '0.1'))
                continue
                
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                continue
            
            if in_code_block:
                elements.append((self._scrub_text(stripped), 'code'))
                continue

            # --- Handle Single Line Explicit Math ---
            if stripped.startswith('$$') and stripped.endswith('$$'):
                elements.append((stripped, 'equation'))
                continue
            
            # --- Handle Implicit Multi-line LaTeX (e.g. \begin{cases} ... \end{cases}) ---
            if stripped.startswith('\\begin{'):
                 in_raw_latex_block = True
                 math_buffer = [stripped]
                 # If it closes on the same line (rare but possible)
                 if '\\end{' in stripped:
                     elements.append((f'$${stripped}$$', 'equation'))
                     in_raw_latex_block = False
                     math_buffer = []
                 continue
            
            if in_raw_latex_block:
                math_buffer.append(stripped)
                if '\\end{' in stripped:
                    full_math = '$$' + ' '.join(math_buffer) + '$$'
                    elements.append((full_math, 'equation'))
                    in_raw_latex_block = False
                    math_buffer = []
                continue

            # --- Handle Single Line Raw LaTeX Indicators ---
            latex_indicators = ['\\frac', '\\int', '\\sum', '\\partial', '\\nabla', '\\boxed', '\\lim']
            # Only match if strictly starts with it or looks like math
            if any(stripped.startswith(ind) for ind in latex_indicators) and not stripped.startswith('$'):
                elements.append((f'$${stripped}$$', 'equation'))
                continue

            # Detect Headers
            if stripped.startswith('# '):
                elements.append((self._scrub_text(stripped[2:].strip()), 'title'))
            elif stripped.startswith('## '):
                elements.append((self._scrub_text(stripped[3:].strip()), 'heading2'))
            elif stripped.startswith('### '):
                elements.append((self._scrub_text(stripped[4:].strip()), 'heading3'))
            elif stripped.startswith('- ') or stripped.startswith('* '):
                elements.append((self._scrub_text(stripped[2:].strip()), 'bullet'))
            elif re.match(r'^\d+\.\s', stripped):
                parts = stripped.split('.', 1)
                content = parts[1].strip() if len(parts) > 1 else ""
                elements.append((self._scrub_text(content), 'numbered'))
            elif stripped.startswith('> '):
                 elements.append((self._scrub_text(stripped[2:].strip()), 'blockquote'))
            else:
                elements.append((self._scrub_text(stripped), 'body'))
        
        return elements

    def _html_escape(self, text: str) -> str:
        replacements = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&apos;'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _process_inline_math(self, text: str) -> str:
        """
        Finds inline math $...$ and replaces it with <img .../> tags pointing to rendered PNGs.
        """
        import tempfile
        
        def replace_math(match):
            latex = html.unescape(match.group(1))
            # Render to bytes
            buf = self.render_equation(latex, dpi=300, fontsize=18, is_inline=True)
            if buf:
                # Save to temp file because reportlab needs a path
                # We need these files to persist until PDF generation is done.
                # Since this is a service, maybe we should clean them up? 
                # For now, OS temp cleanup handles it eventually, or we track them.
                try:
                    # Create a temp file
                    fd, tmp_path = tempfile.mkstemp(suffix=".png")
                    with os.fdopen(fd, 'wb') as f:
                        f.write(buf.getvalue())
                    
                    tmp_path = tmp_path.replace('\\', '/') # ReportLab prefers forward slashes
                    
                    # Calculate approximate height to maintain line height
                    # 14pt font = ~18px height
                    # We make it relative to font size.
                    return f'<img src="{tmp_path}" valign="-4" height="15" />' 
                except Exception as e:
                    logger.error(f"Failed to save inline math img: {e}")
                    return f'<font face="Courier"><i>{latex}</i></font>'
            else:
                return f'<font face="Courier"><i>{latex}</i></font>'

        # Regex for $...$ that is NOT $$...$$
        return re.sub(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', replace_math, text)

    def _format_text_for_reportlab(self, text: str) -> str:
        text = self._html_escape(text)
        
        # Basic Formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        text = re.sub(r'`(.*?)`', r'<font face="Courier">\1</font>', text)
        
        # Inline Math - Render as Images
        # We do this AFTER html escape so $ doesn't get messed up, BUT inside the math we might have < > &
        # Actually `_html_escape` might break latex like `a < b`.
        # So we should process inline math BEFORE html escape?
        # If we do it before, the <img> tags will get escaped.
        # Solution: Extract math, replace with placeholder, escape text, put math back (rendered).
        # Or simpler: Unescape math content inside the replace function.
        text = self._process_inline_math(text)
        
        return text

    def _get_styles(self):
        styles = self.getSampleStyleSheet()
        return {
            'title': self.ParagraphStyle(
                'CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=self.HexColor('#1f2937'),
                spaceAfter=12, fontName='Helvetica-Bold'
            ),
            'heading2': self.ParagraphStyle(
                'CustomHeading2', parent=styles['Heading2'], fontSize=16, textColor=self.HexColor('#374151'),
                spaceAfter=10, fontName='Helvetica-Bold'
            ),
            'heading3': self.ParagraphStyle(
                'CustomHeading3', parent=styles['Heading3'], fontSize=14, textColor=self.HexColor('#4b5563'),
                spaceAfter=8, fontName='Helvetica-Bold'
            ),
            'body': self.ParagraphStyle(
                'CustomBody', parent=styles['BodyText'], fontSize=11, leading=14, alignment=self.TA_JUSTIFY,
                spaceAfter=8, fontName='Helvetica'
            ),
            'bullet': self.ParagraphStyle(
                'CustomBullet', parent=styles['Normal'], fontSize=11, leading=14, leftIndent=20,
                spaceAfter=6, bulletIndent=10, fontName='Helvetica'
            ),
            'numbered': self.ParagraphStyle(
                'CustomNumbered', parent=styles['Normal'], fontSize=11, leading=14, leftIndent=20,
                spaceAfter=6, fontName='Helvetica'
            ),
            'blockquote': self.ParagraphStyle(
                'Blockquote', parent=styles['Normal'], fontSize=10, leading=12, leftIndent=30,
                rightIndent=30, spaceAfter=10, fontName='Helvetica-Oblique', textColor=self.HexColor('#555555')
            ),
            'code': self.ParagraphStyle(
                'Code', parent=styles['Normal'], fontSize=9, leading=11, leftIndent=0, spaceAfter=6,
                fontName='Courier', textColor=self.HexColor('#D14')
            )
        }

    def generate_pdf_from_pages(self, pages_data: list, output_path: str, title: str = None) -> bool:
        try:
            # Create output directory
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Setup Doc
            doc = self.SimpleDocTemplate(
                output_path, pagesize=self.letter,
                rightMargin=0.75 * self.inch, leftMargin=0.75 * self.inch,
                topMargin=0.75 * self.inch, bottomMargin=0.75 * self.inch,
            )
            
            styles = self._get_styles()
            story = []
            
            # Title
            if title:
                story.append(self.Paragraph(self._scrub_text(title), styles['title']))
                story.append(self.Spacer(1, 0.2 * self.inch))
            
            # Process Pages
            for idx, page_text in enumerate(pages_data):
                if idx > 0:
                    story.append(self.PageBreak())
                    story.append(self.Paragraph(f"Page {idx+1}", styles['heading3']))
                    story.append(self.Spacer(1, 0.1 * self.inch))
                
                elements = self._parse_markdown(page_text)
                
                for content, style_type in elements:
                    if style_type == 'spacer':
                         story.append(self.Spacer(1, 0.1 * self.inch))
                         continue
                    
                    if style_type == 'equation':
                        # Render Equation
                        img_buffer = self.render_equation(content)
                        if img_buffer:
                            try:
                                import PIL.Image
                                # Get image aspect ratio to scale appropriately
                                pil_img = PIL.Image.open(img_buffer)
                                i_width, i_height = pil_img.size
                                # Max width constraint (6 inches text width appx)
                                max_w = 6 * self.inch
                                
                                # Scale logic for printing
                                # 300 dpi image. Reportlab points are 1/72.
                                # native size in points:
                                width_pts = i_width * 72 / 300.0
                                height_pts = i_height * 72 / 300.0
                                
                                # If width is too wide, scale down
                                if width_pts > max_w:
                                    scale = max_w / width_pts
                                    width_pts *= scale
                                    height_pts *= scale
                                
                                img_flowable = self.Image(img_buffer, width=width_pts, height=height_pts)
                                img_flowable.hAlign = 'CENTER'
                                story.append(img_flowable)
                                story.append(self.Spacer(1, 0.1 * self.inch))
                            except Exception as img_err:
                                logger.error(f"Image sizing error: {img_err}")
                                # Fallback to text
                                story.append(self.Paragraph(f"<font color='red'>[Equation Error]</font>", styles['body']))
                        else:
                            # Render failed, show raw text
                            story.append(self.Paragraph(self._format_text_for_reportlab(content), styles['code']))
                        continue
                    
                    # Textual Content
                    formatted_text = self._format_text_for_reportlab(content)
                    
                    # Select style
                    style = styles.get(style_type, styles['body'])
                    
                    if style_type == 'bullet' or style_type == 'numbered':
                        story.append(self.Paragraph(f"• {formatted_text}", style))
                    else:
                        story.append(self.Paragraph(formatted_text, style))

            # Build
            doc.build(story)
            logger.info(f"PDF Generated at {output_path}")
            return True
            
        except Exception as e:
            logger.exception(f"PDF Generation Failed: {e}")
            return False

    def generate_pdf(self, text: str, output_path: str) -> bool:
        """Single page wrapper."""
        return self.generate_pdf_from_pages([text], output_path)
