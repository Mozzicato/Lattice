"""
Equation analysis utilities using LLM for deeper understanding
"""
import logging
from typing import Dict, Any, Optional
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class EquationAnalyzer:
    """
    Analyzes equations using LLM to provide explanations and insights.
    """

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def parse_to_sympy(self, latex: str) -> Optional[str]:
        """
        Attempt to parse LaTeX to sympy-compatible format.
        This is a simplified version - in production, use a proper LaTeX parser.
        """
        try:
            # Basic conversions for common cases
            sympy_equiv = latex

            # Handle fractions
            sympy_equiv = sympy_equiv.replace('\\frac{', '(').replace('}{', ')/(').replace('}', ')')

            # Handle powers
            sympy_equiv = sympy_equiv.replace('^{', '**(').replace('}', ')')

            # Handle square roots
            sympy_equiv = sympy_equiv.replace('\\sqrt{', 'sqrt(').replace('}', ')')

            # Handle Greek letters (map to sympy symbols)
            greek_map = {
                '\\alpha': 'alpha',
                '\\beta': 'beta',
                '\\gamma': 'gamma',
                '\\delta': 'delta',
                '\\epsilon': 'epsilon',
                '\\theta': 'theta',
                '\\lambda': 'lambda',
                '\\mu': 'mu',
                '\\pi': 'pi',
                '\\sigma': 'sigma',
                '\\phi': 'phi',
                '\\omega': 'omega'
            }
            for latex_greek, sympy_greek in greek_map.items():
                sympy_equiv = sympy_equiv.replace(latex_greek, sympy_greek)

            return sympy_equiv
        except Exception as e:
            logger.warning(f"Failed to parse LaTeX to sympy: {latex}, error: {e}")
            return None

    async def analyze_equation(self, latex: str, context: str) -> Dict[str, Any]:
        """
        Analyze an equation using LLM to provide explanation and insights.

        Args:
            latex: LaTeX representation of the equation
            context: Surrounding text context

        Returns:
            Analysis results including explanation, variables, etc.
        """
        try:
            prompt = f"""
            Analyze this mathematical equation and provide a detailed explanation:

            Equation (LaTeX): {latex}
            Context: {context}

            Please provide:
            1. What the equation represents
            2. Key variables and their meanings
            3. The mathematical concept or principle it demonstrates
            4. Any assumptions or conditions for validity
            5. How it relates to the surrounding context

            Format your response as JSON with keys: explanation, variables, concept, assumptions, relation_to_context
            """

            response = await self.llm_client.generate_response(prompt)

            # Try to parse as JSON, fallback to structured text
            try:
                import json
                analysis = json.loads(response)
            except:
                # Fallback: create structured response from text
                analysis = {
                    "explanation": response,
                    "variables": "Unable to extract",
                    "concept": "Mathematical equation",
                    "assumptions": "Standard mathematical assumptions",
                    "relation_to_context": "Part of the document content"
                }

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze equation {latex}: {e}")
            return {
                "explanation": f"Equation: {latex}",
                "variables": "Unknown",
                "concept": "Mathematical expression",
                "assumptions": "Standard",
    "relation_to_context": "Embedded in document",
    "error": str(e)
}