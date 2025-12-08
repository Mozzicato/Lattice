"""
Pydantic Schemas for Request/Response Validation
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime


# Document Schemas
class DocumentBase(BaseModel):
    """Base document schema"""
    filename: str


class DocumentCreate(DocumentBase):
    """Schema for creating a document"""
    pass


class DocumentResponse(DocumentBase):
    """Schema for document response"""
    id: str
    raw_text: Optional[str] = None
    doc_metadata: Optional[Dict[str, Any]] = None  # Updated field name
    created_at: datetime
    
    class Config:
        from_attributes = True


# Equation Schemas
class EquationBase(BaseModel):
    """Base equation schema"""
    latex: str
    context: Optional[str] = None


class EquationCreate(EquationBase):
    """Schema for creating an equation"""
    document_id: str
    position: Optional[int] = None
    section_title: Optional[str] = None


class EquationResponse(EquationBase):
    """Schema for equation response"""
    id: str
    document_id: str
    position: Optional[int] = None
    section_title: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# DocumentWithEquations must be defined after EquationResponse
class DocumentWithEquations(DocumentResponse):
    """Document with equations"""
    equations: List["EquationResponse"] = []


# Variable Schema
class Variable(BaseModel):
    """Variable in an equation"""
    name: str
    symbol: str
    description: str
    unit: Optional[str] = None
    variable_type: str  # 'independent', 'dependent', 'constant'
    domain: Optional[tuple] = None


# Derivation Step Schema
class DerivationStep(BaseModel):
    """Single step in a derivation"""
    step_number: int
    expression: str
    explanation: str
    justification: str


# Equation Analysis Schemas
class EquationAnalysisResponse(BaseModel):
    """Schema for equation analysis response"""
    id: str
    equation_id: str
    variables: List[Variable]
    steps: List[DerivationStep]
    explanation: str
    complexity_score: float
    created_at: datetime
    
    class Config:
        from_attributes = True


# Simulation Schemas
class Range(BaseModel):
    """Variable range for simulation"""
    min: float
    max: float
    step: float
    default: float


class PlotConfig(BaseModel):
    """Visualization configuration"""
    plot_type: str
    title: str
    x_label: str
    y_label: str
    z_label: Optional[str] = None


class SimulationResponse(BaseModel):
    """Schema for simulation response"""
    id: str
    equation_id: str
    variables: List[Variable]
    ranges: Dict[str, Range]
    plot_config: PlotConfig
    created_at: datetime
    
    class Config:
        from_attributes = True


class SimulationComputeRequest(BaseModel):
    """Schema for simulation compute request"""
    parameters: Dict[str, float]


class SimulationComputeResponse(BaseModel):
    """Schema for simulation compute response"""
    success: bool
    result: Optional[Dict[str, Any]] = None
    plot_data: Optional[Dict[str, List]] = None
    error: Optional[str] = None
    message: Optional[str] = None


# Question Schemas
class QuestionResponse(BaseModel):
    """Schema for question response"""
    id: str
    equation_id: str
    question_text: str
    question_type: str
    options: List[str]
    difficulty: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class AnswerSubmit(BaseModel):
    """Schema for submitting an answer"""
    answer: str


class Feedback(BaseModel):
    """Schema for answer feedback"""
    correct: bool
    explanation: str
    hints: List[str] = []


# Summary Schemas
class EquationSummary(BaseModel):
    """Summary of a single equation"""
    equation_id: str
    latex: str
    summary: str
    key_variables: List[Variable]
    importance_score: float


class SummaryResponse(BaseModel):
    """Schema for document summary"""
    document_id: str
    document_summary: str
    key_equations: List[EquationSummary]
    insights: List[str]
    recommendations: List[str]
    created_at: datetime


class ExportRequest(BaseModel):
    """Schema for export request"""
    format: str = Field(..., pattern="^(markdown|json|pdf)$")


# Upload Response
class UploadResponse(BaseModel):
    """Schema for upload response"""
    document_id: str
    status: str
    estimated_time: Optional[int] = None
    poll_url: str


# Rebuild models to resolve forward references
DocumentWithEquations.model_rebuild()
