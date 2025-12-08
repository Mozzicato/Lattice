"""
Equation Extraction Service
"""
import re
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEquation:
    """Represents an extracted equation"""
    latex: str
    context: str
    position: int
    raw_match: str


class EquationExtractor:
    """
    Extracts LaTeX equations from document text.
    """
    
    # Regex patterns for different LaTeX equation formats
    PATTERNS = [
        # Display math with $$
        (r'\$\$(.*?)\$\$', 'display'),
        # Inline math with $
        (r'(?<!\$)\$(?!\$)(.*?)\$(?!\$)', 'inline'),
        # equation environment
        (r'\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}', 'equation'),
        # align environment
        (r'\\begin\{align\*?\}(.*?)\\end\{align\*?\}', 'align'),
        # gather environment
        (r'\\begin\{gather\*?\}(.*?)\\end\{gather\*?\}', 'gather'),
        # displaymath environment
        (r'\\begin\{displaymath\}(.*?)\\end\{displaymath\}', 'displaymath'),
        # Bracket notation
        (r'\\\[(.*?)\\\]', 'bracket'),
    ]
    
    CONTEXT_WINDOW = 200  # Characters before and after equation
    
    def __init__(self):
        self.compiled_patterns = [
            (re.compile(pattern, re.DOTALL), eq_type) 
            for pattern, eq_type in self.PATTERNS
        ]
    
    def extract_equations(self, text: str) -> List[ExtractedEquation]:
        """
        Extract all equations from text.
        
        Args:
            text: Document text
            
        Returns:
            List of ExtractedEquation objects
        """
        equations = []
        seen_positions = set()  # Avoid duplicates
        
        for pattern, eq_type in self.compiled_patterns:
            for match in pattern.finditer(text):
                latex = match.group(1).strip()
                position = match.start()
                
                # Skip if we've already found an equation at this position
                if position in seen_positions:
                    continue
                
                # Skip empty equations
                if not latex or len(latex) < 2:
                    continue
                
                # Skip if it looks like it's not really an equation
                if not self._looks_like_equation(latex):
                    continue
                
                seen_positions.add(position)
                
                # Extract context
                context = self._extract_context(text, position, match.end())
                
                equations.append(ExtractedEquation(
                    latex=latex,
                    context=context,
                    position=position,
                    raw_match=match.group(0)
                ))
        
        # Sort by position
        equations.sort(key=lambda x: x.position)
        
        logger.info(f"Extracted {len(equations)} equations from text")
        return equations
    
    def _looks_like_equation(self, latex: str) -> bool:
        """
        Check if the extracted text looks like a real equation.
        
        Args:
            latex: LaTeX string
            
        Returns:
            True if it looks like an equation
        """
        # Must contain at least one letter or number
        if not re.search(r'[a-zA-Z0-9]', latex):
            return False
        
        # Should contain mathematical operators or symbols
        math_indicators = [
            '=', '+', '-', '*', '/', '^', '_',
            '\\frac', '\\int', '\\sum', '\\prod',
            '\\alpha', '\\beta', '\\gamma', '\\theta',
            '\\nabla', '\\partial', '\\Delta',
            '\\sin', '\\cos', '\\tan', '\\log', '\\exp',
            '\\sqrt', '\\leq', '\\geq', '\\neq',
        ]
        
        return any(indicator in latex for indicator in math_indicators)
    
    def _extract_context(self, text: str, start_pos: int, end_pos: int) -> str:
        """
        Extract surrounding context for an equation.
        
        Args:
            text: Full document text
            start_pos: Start position of equation
            end_pos: End position of equation
            
        Returns:
            Context string
        """
        # Get text before and after
        before_start = max(0, start_pos - self.CONTEXT_WINDOW)
        after_end = min(len(text), end_pos + self.CONTEXT_WINDOW)
        
        before = text[before_start:start_pos].strip()
        after = text[end_pos:after_end].strip()
        
        # Clean up context
        context_parts = []
        
        if before:
            # Get last sentence or paragraph
            sentences = re.split(r'[.!?]\s+', before)
            if sentences:
                context_parts.append(sentences[-1])
        
        if after:
            # Get first sentence or paragraph
            sentences = re.split(r'[.!?]\s+', after)
            if sentences:
                context_parts.append(sentences[0])
        
        return ' [...] '.join(context_parts)
    
    def identify_section(self, text: str, position: int) -> str:
        """
        Identify which section an equation belongs to.
        
        Args:
            text: Full document text
            position: Position of equation in text
            
        Returns:
            Section title or empty string
        """
        # Look backward for section headers
        text_before = text[:position]
        
        # Common section header patterns
        section_patterns = [
            r'\n#+\s+(.*?)\n',  # Markdown headers
            r'\n\\section\{(.*?)\}',  # LaTeX sections
            r'\n\\subsection\{(.*?)\}',  # LaTeX subsections
            r'\n([A-Z][A-Za-z\s]+):\n',  # Title case with colon
            r'\n([0-9]+\.)\s+([A-Za-z\s]+)\n',  # Numbered sections
        ]
        
        for pattern in section_patterns:
            matches = list(re.finditer(pattern, text_before))
            if matches:
                # Get the last match (closest to equation)
                last_match = matches[-1]
                return last_match.group(1).strip()
        
        return ""
    
    def clean_latex(self, latex: str) -> str:
        """
        Clean and normalize LaTeX equation.
        
        Args:
            latex: Raw LaTeX string
            
        Returns:
            Cleaned LaTeX string
        """
        # Remove extra whitespace
        latex = ' '.join(latex.split())
        
        # Remove LaTeX comments
        latex = re.sub(r'%.*$', '', latex, flags=re.MULTILINE)
        
        # Normalize spacing around operators
        latex = re.sub(r'\s*=\s*', ' = ', latex)
        latex = re.sub(r'\s*\+\s*', ' + ', latex)
        latex = re.sub(r'\s*-\s*', ' - ', latex)
        
        return latex.strip()
