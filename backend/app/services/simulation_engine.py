"""
Simulation Engine Service
"""
import numpy as np
import sympy
from typing import Dict, Any, List, Optional, Callable
import logging
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)


@dataclass
class Range:
    """Variable range for simulation"""
    min: float
    max: float
    step: float
    default: float


@dataclass
class PlotConfig:
    """Visualization configuration"""
    plot_type: str
    title: str
    x_label: str
    y_label: str
    z_label: Optional[str] = None


class SimulationEngine:
    """
    Creates interactive simulations from equations.
    """
    
    def __init__(self):
        self.max_points = 1000  # Maximum number of plot points
        self.timeout_seconds = 5
    
    def create_simulation(
        self,
        expr: sympy.Expr,
        variables: List[Dict[str, Any]],
        latex: str = ""
    ) -> Dict[str, Any]:
        """
        Generate simulation configuration from equation.
        
        Args:
            expr: SymPy expression
            variables: List of variable dictionaries
            latex: Original LaTeX equation
            
        Returns:
            Simulation configuration dictionary
        """
        # Select manipulable variables
        selected_vars = self._select_key_variables(expr, variables)
        
        if not selected_vars:
            logger.warning("No suitable variables found for simulation")
            return {
                "success": False,
                "error": "No manipulable variables found"
            }
        
        # Determine ranges for each variable
        ranges = self._compute_ranges(expr, selected_vars)
        
        # Create plot configuration
        plot_config = self._create_plot_config(expr, selected_vars, latex)
        
        # Generate initial plot data
        initial_data = self._compute_initial_data(expr, selected_vars, ranges)
        
        return {
            "success": True,
            "variables": selected_vars,
            "ranges": {var['name']: asdict(r) for var, r in zip(selected_vars, ranges.values())},
            "plot_config": asdict(plot_config),
            "initial_data": initial_data,
            "latex": latex
        }
    
    def _select_key_variables(
        self, 
        expr: sympy.Expr, 
        variables: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Select 1-3 key variables for manipulation.
        
        Args:
            expr: SymPy expression
            variables: All available variables
            
        Returns:
            List of selected variable dictionaries
        """
        # Filter out constants
        non_constants = [
            v for v in variables 
            if v.get('variable_type') != 'constant'
        ]
        
        # Limit to 3 variables for simplicity
        selected = non_constants[:3]
        
        logger.info(f"Selected {len(selected)} variables for simulation")
        return selected
    
    def _compute_ranges(
        self, 
        expr: sympy.Expr, 
        variables: List[Dict[str, Any]]
    ) -> Dict[str, Range]:
        """
        Determine sensible ranges for each variable.
        
        Args:
            expr: SymPy expression
            variables: Selected variables
            
        Returns:
            Dictionary mapping variable names to Range objects
        """
        ranges = {}
        
        for var in variables:
            var_name = var['name']
            
            # Check for physical constraints
            if var_name.lower() in ['mass', 'distance', 'time', 'r', 'h', 't']:
                min_val = 0.0
            else:
                min_val = -10.0
            
            # Estimate reasonable maximum
            max_val = self._estimate_max_value(var_name)
            
            # Ensure numerical stability
            if max_val <= min_val:
                max_val = min_val + 10.0
            
            step = (max_val - min_val) / 100.0
            default = (min_val + max_val) / 2.0
            
            ranges[var_name] = Range(
                min=min_val,
                max=max_val,
                step=step,
                default=default
            )
        
        return ranges
    
    def _estimate_max_value(self, var_name: str) -> float:
        """
        Estimate a reasonable maximum value for a variable.
        
        Args:
            var_name: Variable name
            
        Returns:
            Estimated maximum value
        """
        # Domain-specific knowledge
        max_values = {
            'mass': 100.0,
            'm': 100.0,
            'time': 100.0,
            't': 100.0,
            'velocity': 100.0,
            'v': 100.0,
            'distance': 100.0,
            'x': 100.0,
            'y': 100.0,
            'z': 100.0,
            'angle': 2 * np.pi,
            'theta': 2 * np.pi,
            'temperature': 500.0,
            'T': 500.0,
        }
        
        return max_values.get(var_name.lower(), 10.0)
    
    def _create_plot_config(
        self,
        expr: sympy.Expr,
        variables: List[Dict[str, Any]],
        latex: str
    ) -> PlotConfig:
        """
        Create plot configuration.
        
        Args:
            expr: SymPy expression
            variables: Selected variables
            latex: LaTeX equation
            
        Returns:
            PlotConfig object
        """
        if len(variables) == 1:
            plot_type = "line"
            x_label = f"{variables[0]['description']} ({variables[0].get('unit', '')})"
            y_label = "Output"
        elif len(variables) == 2:
            plot_type = "heatmap"
            x_label = f"{variables[0]['description']} ({variables[0].get('unit', '')})"
            y_label = f"{variables[1]['description']} ({variables[1].get('unit', '')})"
        else:
            plot_type = "3d"
            x_label = f"{variables[0]['description']} ({variables[0].get('unit', '')})"
            y_label = f"{variables[1]['description']} ({variables[1].get('unit', '')})"
        
        title = f"Equation Visualization"
        if latex:
            title = f"${latex[:50]}...$" if len(latex) > 50 else f"${latex}$"
        
        return PlotConfig(
            plot_type=plot_type,
            title=title,
            x_label=x_label,
            y_label=y_label
        )
    
    def _compute_initial_data(
        self,
        expr: sympy.Expr,
        variables: List[Dict[str, Any]],
        ranges: Dict[str, Range]
    ) -> Dict[str, Any]:
        """
        Compute initial plot data.
        
        Args:
            expr: SymPy expression
            variables: Selected variables
            ranges: Variable ranges
            
        Returns:
            Plot data dictionary
        """
        if len(variables) == 1:
            return self._compute_1d_data(expr, variables[0], ranges[variables[0]['name']])
        elif len(variables) == 2:
            return self._compute_2d_data(expr, variables, ranges)
        else:
            # For 3+ variables, just use default values for extras
            return self._compute_2d_data(expr, variables[:2], ranges)
    
    def _compute_1d_data(
        self,
        expr: sympy.Expr,
        variable: Dict[str, Any],
        var_range: Range
    ) -> Dict[str, Any]:
        """Compute 1D line plot data"""
        var_name = variable['name']
        var_symbol = sympy.Symbol(var_name)
        
        # Create numpy function
        try:
            func = sympy.lambdify(var_symbol, expr, modules=['numpy'])
        except Exception as e:
            logger.error(f"Could not create lambda function: {e}")
            return {"error": str(e)}
        
        # Generate x values
        x_vals = np.linspace(var_range.min, var_range.max, 100)
        
        # Compute y values
        try:
            y_vals = func(x_vals)
            
            # Handle complex numbers
            if np.iscomplexobj(y_vals):
                y_vals = np.real(y_vals)
            
            # Handle infinities and NaNs
            mask = np.isfinite(y_vals)
            x_vals = x_vals[mask]
            y_vals = y_vals[mask]
            
        except Exception as e:
            logger.error(f"Error computing values: {e}")
            return {"error": str(e)}
        
        return {
            "x": x_vals.tolist(),
            "y": y_vals.tolist(),
            "type": "line"
        }
    
    def _compute_2d_data(
        self,
        expr: sympy.Expr,
        variables: List[Dict[str, Any]],
        ranges: Dict[str, Range]
    ) -> Dict[str, Any]:
        """Compute 2D heatmap data"""
        var1_name = variables[0]['name']
        var2_name = variables[1]['name']
        
        var1_symbol = sympy.Symbol(var1_name)
        var2_symbol = sympy.Symbol(var2_name)
        
        # Create numpy function
        try:
            func = sympy.lambdify([var1_symbol, var2_symbol], expr, modules=['numpy'])
        except Exception as e:
            logger.error(f"Could not create lambda function: {e}")
            return {"error": str(e)}
        
        # Generate grid
        var1_range = ranges[var1_name]
        var2_range = ranges[var2_name]
        
        x = np.linspace(var1_range.min, var1_range.max, 50)
        y = np.linspace(var2_range.min, var2_range.max, 50)
        X, Y = np.meshgrid(x, y)
        
        # Compute Z values
        try:
            Z = func(X, Y)
            
            # Handle complex numbers
            if np.iscomplexobj(Z):
                Z = np.real(Z)
            
            # Replace infinities and NaNs
            Z = np.nan_to_num(Z, nan=0.0, posinf=1e10, neginf=-1e10)
            
        except Exception as e:
            logger.error(f"Error computing 2D values: {e}")
            return {"error": str(e)}
        
        return {
            "x": x.tolist(),
            "y": y.tolist(),
            "z": Z.tolist(),
            "type": "heatmap"
        }
    
    def compute_point(
        self,
        expr: sympy.Expr,
        parameters: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Compute equation output for specific parameter values.
        
        Args:
            expr: SymPy expression
            parameters: Dictionary of parameter values
            
        Returns:
            Computation result
        """
        try:
            # Create symbols for all parameters
            symbols = {name: sympy.Symbol(name) for name in parameters.keys()}
            
            # Substitute values
            result = expr.subs(symbols)
            
            # Evaluate to number
            result_val = float(result.evalf())
            
            return {
                "success": True,
                "result": result_val,
                "parameters": parameters
            }
            
        except (ValueError, ZeroDivisionError, TypeError) as e:
            logger.warning(f"Computation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "parameters": parameters
            }
        except Exception as e:
            logger.error(f"Unexpected error in computation: {e}")
            return {
                "success": False,
                "error": "Computation failed",
                "parameters": parameters
            }
