"""
Equation Analysis API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.schemas import EquationResponse, EquationAnalysisResponse
from app.models import Equation, EquationAnalysis
from app.services.equation_analyzer import EquationAnalyzer
from app.services.llm_client import LLMClient

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/equations/{equation_id}/analysis", response_model=EquationAnalysisResponse)
async def get_equation_analysis(equation_id: str, db: Session = Depends(get_db)):
    """
    Get analysis for a specific equation
    """
    # Get equation
    equation = db.query(Equation).filter(Equation.id == equation_id).first()
    if not equation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equation {equation_id} not found"
        )
    
    # Get or create analysis
    analysis = db.query(EquationAnalysis).filter(
        EquationAnalysis.equation_id == equation_id
    ).first()
    
    if not analysis:
        # TODO: Trigger analysis generation
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis not yet available for equation {equation_id}"
        )
    
    return analysis


@router.post("/equations/{equation_id}/analyze", response_model=EquationAnalysisResponse)
async def analyze_equation(equation_id: str, db: Session = Depends(get_db)):
    """
    Trigger analysis for a specific equation
    """
    equation = db.query(Equation).filter(Equation.id == equation_id).first()
    if not equation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equation {equation_id} not found"
        )
    
    # Check if analysis already exists
    existing_analysis = db.query(EquationAnalysis).filter(
        EquationAnalysis.equation_id == equation_id
    ).first()
    
    if existing_analysis:
        return existing_analysis
    
    # Perform analysis
    try:
        llm_client = LLMClient()
        analyzer = EquationAnalyzer(llm_client=llm_client)
        analysis_result = analyzer.analyze_equation(equation.latex, equation.context or "")
        
        if not analysis_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=analysis_result.get("error", "Analysis failed")
            )
        
        # Create analysis record
        analysis = EquationAnalysis(
            equation_id=equation_id,
            variables=analysis_result["variables"],
            steps=[],  # Steps generation can be added later
            explanation=analysis_result["explanation"],
            complexity_score=analysis_result["complexity_score"]
        )
        
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        logger.info(f"Analysis created for equation {equation_id}")
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing equation {equation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )
