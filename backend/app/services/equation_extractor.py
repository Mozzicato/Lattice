"""
Equation extraction and LaTeX conversion utilities
"""
import re
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ExtractedEquation:
    """Represents an extracted equation with its LaTeX representation and context."""
    latex: str
    context: str
    position: int  # Character position in the text


class EquationExtractor:
    """
    Extracts mathematical equations from text and converts them to LaTeX format.
    """

    def __init__(self):
        # Common math patterns to detect
        self.equation_patterns = [
            # Basic equations like x = y + z
            r'([a-zA-Z]\w*\s*=\s*[^=\n]+)',
            # Function forms like x(t) = ...
            r'([a-zA-Z]\w*\([^\)]*\)\s*=\s*[^=\n]+)',
            # Fractions like a/b or 1/2
            r'(\d+\s*/\s*\d+|[a-zA-Z]\w*\s*/\s*[a-zA-Z]\w*)',
            # Powers like x^2
            r'([a-zA-Z]\w*\^\d+)',
            # Square roots like sqrt(x)
            r'(sqrt\([^)]+\))',
            # Greek letters and symbols
            r'(\b(alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|phi|omega)\b)',
            # Trig functions and cos/sin/tan
            r'\b(cos|sin|tan|sec|csc|cot)\s*\([^\)]+\)',
            # Derivatives like d/dx or x''
            r'(d/d[a-zA-Z]|[a-zA-Z]\s*\'\')',
            # Integrals like ∫_0^T f(t) dt
            r'(∫[^∫]*d[a-zA-Z])',
            # Summation like Σ_{i=1}^{n} i or other variants
            r'(∑\s*_\{[^}]+\}\s*\^\{[^}]+\}\s*[^=\n]+)',
            r'(∑\s*_\{[^}]+\}\s*[^=\n]+)',
        ]

    def extract_equations(self, text: str) -> List[ExtractedEquation]:
        """
        Extract equations from text and convert to LaTeX.

        Args:
            text: The raw text content

        Returns:
            List of extracted equations with LaTeX representations
        """
        equations = []

        # Find all potential equation regions
        for pattern in self.equation_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                equation_text = match.group(0).strip()

                # Convert to LaTeX
                latex = self._convert_to_latex(equation_text)

                # Get context (surrounding text)
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end].replace('\n', ' ').strip()

                equations.append(ExtractedEquation(
                    latex=latex,
                    context=context,
                    position=match.start()
                ))

        # Remove duplicates based on position
        unique_equations = []
        seen_positions = set()
        for eq in equations:
            if eq.position not in seen_positions:
                unique_equations.append(eq)
                seen_positions.add(eq.position)

        return unique_equations

    def _convert_to_latex(self, equation_text: str) -> str:
        """
        Convert plain text math to LaTeX format.
        """
        latex = equation_text

        # Handle fractions
        latex = re.sub(r'(\d+)/(\d+)', r'\\frac{\1}{\2}', latex)

        # Handle powers
        latex = re.sub(r'([a-zA-Z]\w*)\^(\d+)', r'\1^{\2}', latex)

        # Handle square roots
        latex = re.sub(r'sqrt\(([^)]+)\)', r'\\sqrt{\1}', latex)

        # Handle Greek letters
        greek_map = {
            'alpha': '\\alpha',
            'beta': '\\beta',
            'gamma': '\\gamma',
            'delta': '\\delta',
            'epsilon': '\\epsilon',
            'theta': '\\theta',
            'lambda': '\\lambda',
            'mu': '\\mu',
            'pi': '\\pi',
            'sigma': '\\sigma',
            'phi': '\\phi',
            'omega': '\\omega'
        }
        for greek, latex_greek in greek_map.items():
            # Use a callable replacement to avoid backslash/group interpretation in replacement string
            latex = re.sub(rf'\b{greek}\b', (lambda _m, lg=latex_greek: lg), latex, flags=re.IGNORECASE)

        # Handle derivatives
        latex = re.sub(r'd/d([a-zA-Z])', r'\\frac{d}{d\1}', latex)

        # Handle integrals (basic)
        latex = re.sub(r'∫([^∫]*)d([a-zA-Z])', r'\\int \1 \\, d\2', latex)

        # Handle summations like ∑_{i=1}^{n} i
        latex = re.sub(r'∑\s*_\{([^}]*)\}\s*\^\{([^}]*)\}\s*([^\n]+)', lambda m: f"\\sum_{{{m.group(1)}}}^{{{m.group(2)}}} {m.group(3)}", latex)
        # Handle simpler summation like ∑_{i=1}^{n} i (no ^{})
        latex = re.sub(r'∑\s*_\{([^}]*)\}\s*([^\n]+)', lambda m: f"\\sum_{{{m.group(1)}}} {m.group(2)}", latex)

        return latex

    def identify_section(self, full_text: str, position: int) -> str:
        """
        Identify which section of the document an equation belongs to.
        """
        # Look backwards from the position to find section headers
        text_before = full_text[:position]

        # Common section patterns
        section_patterns = [
            r'#+\s*([^\n]+)',  # Markdown headers
            r'(\d+\.?\d*\s+[A-Z][^\n]+)',  # Numbered sections
            r'(Chapter\s+\d+|[A-Z][^.\n]*:)',  # Chapter headers
        ]

        for pattern in section_patterns:
            matches = list(re.finditer(pattern, text_before, re.IGNORECASE))
            if matches:
                return matches[-1].group(1).strip()

        return "General"