"""
Simulation API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.schemas import SimulationResponse, SimulationComputeRequest, SimulationComputeResponse
from app.models import Simulation, Equation, EquationAnalysis
from app.services.simulation_engine import SimulationEngine
from app.services.equation_analyzer import EquationAnalyzer
import sympy

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/equations/{equation_id}/simulation", response_model=SimulationResponse)
async def get_simulation(equation_id: str, db: Session = Depends(get_db)):
    """
    Get simulation configuration for an equation
    """
    # Check if simulation exists
    simulation = db.query(Simulation).filter(
        Simulation.equation_id == equation_id
    ).first()
    
    if simulation:
        return simulation
    
    # Create simulation if it doesn't exist
    equation = db.query(Equation).filter(Equation.id == equation_id).first()
    if not equation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equation {equation_id} not found"
        )
    
    # Get or create analysis first
    analysis = db.query(EquationAnalysis).filter(
        EquationAnalysis.equation_id == equation_id
    ).first()
    
    if not analysis:
        # Create analysis first
        analyzer = EquationAnalyzer()
        analysis_result = analyzer.analyze_equation(equation.latex, equation.context or "")
        
        if not analysis_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not analyze equation for simulation"
            )
        
        analysis = EquationAnalysis(
            equation_id=equation_id,
            variables=analysis_result["variables"],
            steps=[],
            explanation=analysis_result["explanation"],
            complexity_score=analysis_result["complexity_score"]
        )
        db.add(analysis)
        db.commit()
    
    # Create simulation
    try:
        analyzer = EquationAnalyzer()
        expr = analyzer.parse_to_sympy(equation.latex)
        
        if expr is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not parse equation for simulation"
            )
        
        engine = SimulationEngine()
        sim_config = engine.create_simulation(
            expr,
            analysis.variables,
            equation.latex
        )
        
        if not sim_config.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=sim_config.get("error", "Could not create simulation")
            )
        
        # Save simulation
        simulation = Simulation(
            equation_id=equation_id,
            variables=sim_config["variables"],
            ranges=sim_config["ranges"],
            plot_config=sim_config["plot_config"]
        )
        db.add(simulation)
        db.commit()
        db.refresh(simulation)
        
        logger.info(f"Simulation created for equation {equation_id}")
        return simulation
        
    except Exception as e:
        logger.error(f"Error creating simulation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation creation failed: {str(e)}"
        )


@router.post("/simulations/{simulation_id}/compute", response_model=SimulationComputeResponse)
async def compute_simulation(
    simulation_id: str,
    request: SimulationComputeRequest,
    db: Session = Depends(get_db)
):
    """
    Compute simulation output for given parameters
    """
    simulation = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found"
        )
    
    # Get the equation
    equation = db.query(Equation).filter(Equation.id == simulation.equation_id).first()
    
    try:
        analyzer = EquationAnalyzer()
        expr = analyzer.parse_to_sympy(equation.latex)
        
        if expr is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not parse equation"
            )
        
        engine = SimulationEngine()
        result = engine.compute_point(expr, request.parameters)
        
        return SimulationComputeResponse(
            success=result.get("success", False),
            result=result.get("result"),
            error=result.get("error"),
            parameters=request.parameters
        )
        
    except Exception as e:
        logger.error(f"Error computing simulation: {e}")
        return SimulationComputeResponse(
            success=False,
            result=None,
            error=str(e),
            parameters=request.parameters
        )
