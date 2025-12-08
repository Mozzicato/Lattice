"""
Equation Analysis Service
"""
import sympy
from sympy.parsing.latex import parse_latex
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass, asdict
import json
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class Variable:
    """Represents a variable in an equation"""
    name: str
    symbol: str
    description: str
    unit: Optional[str] = None
    variable_type: str = "independent"  # independent, dependent, constant
    domain: Optional[tuple] = None


@dataclass
class DerivationStep:
    """Represents a step in equation derivation"""
    step_number: int
    expression: str
    explanation: str
    justification: str


class EquationAnalyzer:
    """
    Analyzes equations and generates explanations.
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def parse_to_sympy(self, latex: str) -> Optional[sympy.Expr]:
        """
        Parse LaTeX equation to SymPy expression.
        
        Args:
            latex: LaTeX equation string
            
        Returns:
            SymPy expression or None if parsing fails
        """
        try:
            # Try direct parsing
            expr = parse_latex(latex)
            logger.info(f"Successfully parsed equation: {latex[:50]}...")
            return expr
        except Exception as e:
            logger.warning(f"Failed to parse LaTeX: {e}")
            
            # Try some common fixes
            try:
                # Remove equation environments if present
                cleaned = latex.replace('\\begin{equation}', '').replace('\\end{equation}', '')
                cleaned = cleaned.replace('\\begin{align}', '').replace('\\end{align}', '')
                cleaned = cleaned.strip()
                
                expr = parse_latex(cleaned)
                logger.info(f"Successfully parsed after cleaning")
                return expr
            except Exception as e2:
                logger.error(f"Could not parse equation even after cleaning: {e2}")
                return None
    
    def extract_variables(self, expr: sympy.Expr) -> List[Variable]:
        """
        Extract variables from SymPy expression.
        
        Args:
            expr: SymPy expression
            
        Returns:
            List of Variable objects
        """
        variables = []
        
        # Get all symbols
        symbols = expr.free_symbols
        
        for sym in symbols:
            # Determine if it's likely a constant based on name
            is_constant = self._is_likely_constant(str(sym))
            
            var = Variable(
                name=str(sym),
                symbol=str(sym),
                description=self._generate_variable_description(str(sym)),
                variable_type="constant" if is_constant else "independent",
                unit=self._guess_unit(str(sym))
            )
            variables.append(var)
        
        logger.info(f"Extracted {len(variables)} variables from expression")
        return variables
    
    def _is_likely_constant(self, symbol: str) -> bool:
        """Check if a symbol is likely a constant"""
        constants = {
            'c', 'e', 'pi', 'π', 'g', 'h', 'k', 'G', 'R',
            'epsilon', 'mu', 'sigma', 'hbar'
        }
        return symbol.lower() in constants
    
    def _generate_variable_description(self, symbol: str) -> str:
        """Generate a description for a variable based on its symbol"""
        descriptions = {
            'E': 'Energy',
            'F': 'Force',
            'm': 'Mass',
            'v': 'Velocity',
            'a': 'Acceleration',
            't': 'Time',
            'x': 'Position',
            'y': 'Position',
            'z': 'Position',
            'r': 'Radius',
            'theta': 'Angle',
            'omega': 'Angular velocity',
            'alpha': 'Angular acceleration',
            'T': 'Temperature',
            'P': 'Pressure',
            'V': 'Volume',
            'n': 'Number',
            'c': 'Speed of light',
            'g': 'Gravitational acceleration',
            'h': 'Height',
            'k': 'Constant',
            'G': 'Gravitational constant',
        }
        return descriptions.get(symbol, symbol)
    
    def _guess_unit(self, symbol: str) -> Optional[str]:
        """Guess the unit for a variable"""
        units = {
            'E': 'joules',
            'F': 'newtons',
            'm': 'kilograms',
            'v': 'meters per second',
            'a': 'meters per second squared',
            't': 'seconds',
            'x': 'meters',
            'y': 'meters',
            'z': 'meters',
            'r': 'meters',
            'T': 'kelvin',
            'P': 'pascals',
            'V': 'cubic meters',
            'c': 'meters per second',
            'g': 'meters per second squared',
            'h': 'meters',
        }
        return units.get(symbol)
    
    def analyze_equation(
        self, 
        latex: str, 
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Perform complete analysis of an equation.
        
        Args:
            latex: LaTeX equation string
            context: Surrounding context
            
        Returns:
            Dictionary with analysis results
        """
        # Parse to SymPy
        expr = self.parse_to_sympy(latex)
        
        if expr is None:
            return {
                "success": False,
                "error": "Could not parse equation",
                "latex": latex
            }
        
        # Extract components
        variables = self.extract_variables(expr)
        
        # Generate explanation using LLM if available
        if self.llm_client:
            try:
                # Convert variables to dict format for LLM
                var_dicts = [asdict(v) for v in variables]
                
                explanation = self.llm_client.generate_equation_explanation(
                    latex=latex,
                    variables=var_dicts,
                    context=context
                )
            except Exception as e:
                logger.warning(f"LLM explanation failed: {e}, using basic explanation")
                explanation = self._generate_basic_explanation(expr, variables, context)
        else:
            explanation = self._generate_basic_explanation(expr, variables, context)
        
        # Calculate complexity
        complexity = self._calculate_complexity(expr)
        
        return {
            "success": True,
            "latex": latex,
            "sympy_str": str(expr),
            "variables": [asdict(v) for v in variables],
            "explanation": explanation,
            "complexity_score": complexity,
            "context": context
        }
    
    def _generate_basic_explanation(
        self, 
        expr: sympy.Expr, 
        variables: List[Variable],
        context: str
    ) -> str:
        """
        Generate a basic explanation without LLM.
        
        Args:
            expr: SymPy expression
            variables: List of variables
            context: Surrounding context
            
        Returns:
            Explanation string
        """
        var_names = [v.description for v in variables]
        
        explanation = f"This equation relates {', '.join(var_names)}. "
        
        # Check for specific patterns
        if len(variables) == 2:
            explanation += f"It shows how {var_names[0]} depends on {var_names[1]}."
        elif len(variables) > 2:
            explanation += f"It shows the relationship between these quantities."
        
        # Check for specific operations
        if expr.has(sympy.Derivative):
            explanation += " The equation involves derivatives, indicating rates of change."
        
        if expr.has(sympy.Integral):
            explanation += " The equation involves integration, indicating accumulation or area."
        
        return explanation
    
    def _calculate_complexity(self, expr: sympy.Expr) -> float:
        """
        Calculate complexity score for an equation.
        
        Args:
            expr: SymPy expression
            
        Returns:
            Complexity score between 0 and 1
        """
        # Count operations
        num_operations = len(expr.atoms(sympy.Function)) + len(expr.atoms(sympy.Pow))
        num_variables = len(expr.free_symbols)
        
        # Simple heuristic
        complexity = min(1.0, (num_operations + num_variables) / 20.0)
        
        return round(complexity, 2)
    
    def generate_steps(
        self, 
        expr: sympy.Expr, 
        context: str = ""
    ) -> List[DerivationStep]:
        """
        Generate step-by-step derivation.
        
        Args:
            expr: SymPy expression
            context: Context for derivation
            
        Returns:
            List of DerivationStep objects
        """
        steps = []
        
        # For now, just create a simple step
        # In production, this would use LLM or more sophisticated logic
        steps.append(DerivationStep(
            step_number=1,
            expression=str(expr),
            explanation="Starting equation",
            justification="Given equation from the problem"
        ))
        
        # Try to simplify
        simplified = sympy.simplify(expr)
        if simplified != expr:
            steps.append(DerivationStep(
                step_number=2,
                expression=str(simplified),
                explanation="Simplified form",
                justification="Algebraic simplification"
            ))
        
        return steps
    
    def solve_for_variable(
        self, 
        expr: sympy.Expr, 
        variable: str
    ) -> Optional[sympy.Expr]:
        """
        Solve equation for a specific variable.
        
        Args:
            expr: SymPy expression (should be an equation)
            variable: Variable to solve for
            
        Returns:
            Solution expression or None
        """
        try:
            var_symbol = sympy.Symbol(variable)
            
            # If it's an equality, solve it
            if isinstance(expr, sympy.Equality):
                solutions = sympy.solve(expr, var_symbol)
                if solutions:
                    return solutions[0] if len(solutions) == 1 else solutions
            else:
                # Assume expr = 0
                solutions = sympy.solve(expr, var_symbol)
                if solutions:
                    return solutions[0] if len(solutions) == 1 else solutions
            
            return None
        except Exception as e:
            logger.error(f"Could not solve for {variable}: {e}")
            return None
