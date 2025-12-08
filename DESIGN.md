# Lattice — Detailed Design Document

## Document Information

- **Project:** Lattice MVP
- **Version:** 1.0
- **Date:** December 6, 2025
- **Status:** Draft

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Component Design](#3-component-design)
4. [Data Models](#4-data-models)
5. [API Design](#5-api-design)
6. [Frontend Design](#6-frontend-design)
7. [Processing Pipeline](#7-processing-pipeline)
8. [Security & Performance](#8-security--performance)
9. [Deployment Strategy](#9-deployment-strategy)
10. [Testing Strategy](#10-testing-strategy)
11. [Future Considerations](#11-future-considerations)

---

## 1. Executive Summary

### 1.1 Project Vision

Lattice transforms how students and researchers interact with complex academic material by providing AI-powered, interactive explanations that promote deep understanding rather than passive reading.

### 1.2 Success Metrics

- **User Engagement:** Average session time > 15 minutes
- **Learning Outcomes:** 80% of users report improved understanding
- **System Performance:** < 5 seconds for equation extraction, < 10 seconds for visualization generation
- **User Satisfaction:** NPS score > 40

### 1.3 MVP Constraints

- Single-user sessions (no collaboration)
- Processing limited to text-based PDFs
- Support for mathematical/physics domains initially
- Local deployment only
- Maximum file size: 10MB
- Maximum processing time: 60 seconds per document

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend Layer                       │
│  (React SPA - Upload, Explore, Visualize, Summarize)       │
└────────────────┬────────────────────────────────────────────┘
                 │ REST API (JSON)
┌────────────────▼────────────────────────────────────────────┐
│                      API Gateway (FastAPI)                   │
│              (Authentication, Rate Limiting, Routing)        │
└────┬──────────┬──────────┬──────────┬──────────┬───────────┘
     │          │          │          │          │
┌────▼────┐ ┌──▼──────┐ ┌─▼────────┐ ┌▼────────┐ ┌▼──────────┐
│Document │ │Equation │ │Simulation│ │Assessment│ │Summary    │
│Parser   │ │Analyzer │ │Engine    │ │Engine    │ │Generator  │
└────┬────┘ └──┬──────┘ └─┬────────┘ └┬────────┘ └┬──────────┘
     │         │           │           │           │
     └─────────┴───────────┴───────────┴───────────┘
                         │
              ┌──────────▼──────────┐
              │   Storage Layer     │
              │ (File System + DB)  │
              └─────────────────────┘
```

### 2.2 Technology Stack

#### Backend
- **Framework:** FastAPI 0.104+
- **Python Version:** 3.11+
- **Core Libraries:**
  - `pypdf2` or `pdfplumber` - PDF parsing
  - `sympy` - Symbolic mathematics
  - `numpy` - Numerical computations
  - `scipy` - Scientific computing
  - `langchain` - LLM orchestration
  - `openai` / `anthropic` - LLM providers

#### Frontend
- **Framework:** React 18+ with TypeScript
- **State Management:** Zustand or Redux Toolkit
- **Visualization:** 
  - Plotly.js - Interactive plots
  - React-Plotly.js - React bindings
  - MathJax or KaTeX - Equation rendering
- **UI Components:** Material-UI or shadcn/ui
- **Build Tool:** Vite

#### Storage
- **Document Storage:** Local file system (./uploads/)
- **Session Data:** SQLite (MVP) → PostgreSQL (production)
- **Cache:** Redis (optional for MVP)

#### DevOps
- **Containerization:** Docker + Docker Compose
- **Testing:** pytest (backend), Jest + React Testing Library (frontend)
- **CI/CD:** GitHub Actions

---

## 3. Component Design

### 3.1 Document Parser Component

#### Responsibilities
- Accept PDF/text uploads
- Extract raw text and metadata
- Identify document structure (sections, equations, figures)
- Extract embedded images for OCR (future)

#### Implementation Details

```python
class DocumentParser:
    """
    Parses uploaded documents and extracts structured content.
    """
    
    def __init__(self, llm_client, max_size_mb=10):
        self.llm_client = llm_client
        self.max_size_mb = max_size_mb
        
    def parse(self, file_path: str) -> Document:
        """
        Main parsing entry point.
        
        Returns:
            Document: Structured document object
        """
        # Validate file
        self._validate_file(file_path)
        
        # Extract text
        raw_text = self._extract_text(file_path)
        
        # Structure identification
        sections = self._identify_sections(raw_text)
        
        # Extract equations
        equations = self._extract_equations(raw_text)
        
        return Document(
            raw_text=raw_text,
            sections=sections,
            equations=equations,
            metadata=self._extract_metadata(file_path)
        )
    
    def _extract_equations(self, text: str) -> List[Equation]:
        """
        Extract LaTeX equations using regex + LLM validation.
        """
        # Regex patterns for LaTeX
        patterns = [
            r'\$\$(.*?)\$\$',  # Display math
            r'\$(.*?)\$',       # Inline math
            r'\\begin\{equation\}(.*?)\\end\{equation\}',
            r'\\begin\{align\}(.*?)\\end\{align\}'
        ]
        
        # Extract candidates
        candidates = []
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            candidates.extend(matches)
        
        # Validate and enrich with LLM
        equations = []
        for candidate in candidates:
            equation = self._validate_equation(candidate)
            if equation:
                equations.append(equation)
        
        return equations
```

#### Data Flow
```
File Upload → Validation → Text Extraction → 
Structure Detection → Equation Identification → 
LLM Enhancement → Document Object
```

---

### 3.2 Equation Analyzer Component

#### Responsibilities
- Parse LaTeX equations into symbolic representations
- Identify variables, constants, and operators
- Generate step-by-step derivations
- Create natural language explanations

#### Implementation Details

```python
class EquationAnalyzer:
    """
    Analyzes equations and generates explanations.
    """
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        
    def analyze(self, equation: Equation) -> EquationAnalysis:
        """
        Perform complete analysis of an equation.
        """
        # Parse to SymPy
        sympy_expr = self._parse_to_sympy(equation.latex)
        
        # Extract components
        variables = self._extract_variables(sympy_expr)
        constants = self._extract_constants(sympy_expr)
        
        # Generate explanation steps
        steps = self._generate_steps(sympy_expr, equation.context)
        
        # Create natural language explanation
        explanation = self._generate_explanation(
            sympy_expr, 
            steps, 
            equation.context
        )
        
        return EquationAnalysis(
            equation=equation,
            sympy_expression=sympy_expr,
            variables=variables,
            constants=constants,
            steps=steps,
            explanation=explanation
        )
    
    def _generate_steps(self, expr, context: str) -> List[Step]:
        """
        Generate step-by-step derivation using LLM.
        """
        prompt = f"""
        Given the equation: {expr}
        Context: {context}
        
        Break this down into clear, logical steps.
        For each step:
        1. Show the mathematical transformation
        2. Explain why this step is valid
        3. Highlight key insights
        
        Format as JSON array of steps.
        """
        
        response = self.llm_client.complete(prompt)
        steps = self._parse_steps_response(response)
        
        # Validate steps with SymPy
        validated_steps = self._validate_steps(expr, steps)
        
        return validated_steps
```

#### LLM Integration Strategy

**Prompt Template for Explanations:**
```
You are a patient mathematics tutor explaining to an undergraduate student.

Equation: {equation}
Variables: {variables}
Context: {context}

Provide:
1. A one-sentence intuitive explanation
2. Step-by-step mathematical derivation (3-5 steps)
3. Physical/conceptual interpretation
4. Common misconceptions or pitfalls
5. Real-world applications or examples

Keep explanations clear, avoiding unnecessary jargon.
```

---

### 3.3 Simulation Engine Component

#### Responsibilities
- Generate interactive parameter spaces
- Compute function outputs across ranges
- Create plot configurations for frontend
- Handle numerical edge cases

#### Implementation Details

```python
class SimulationEngine:
    """
    Creates interactive simulations from equations.
    """
    
    def create_simulation(
        self, 
        equation_analysis: EquationAnalysis
    ) -> Simulation:
        """
        Generate simulation configuration.
        """
        # Identify manipulable variables
        variables = self._select_key_variables(
            equation_analysis.variables
        )
        
        # Determine reasonable ranges
        variable_ranges = self._compute_ranges(
            equation_analysis.sympy_expression,
            variables
        )
        
        # Create compute function
        compute_fn = self._create_compute_function(
            equation_analysis.sympy_expression,
            variables
        )
        
        # Generate initial plot data
        initial_data = self._compute_plot_data(
            compute_fn,
            variable_ranges
        )
        
        return Simulation(
            variables=variables,
            ranges=variable_ranges,
            compute_function=compute_fn,
            plot_config=self._create_plot_config(
                equation_analysis,
                initial_data
            )
        )
    
    def _compute_ranges(
        self, 
        expr: sympy.Expr, 
        variables: List[Variable]
    ) -> Dict[str, Range]:
        """
        Determine sensible ranges for each variable.
        """
        ranges = {}
        
        for var in variables:
            # Check for physical constraints
            if var.name in ['mass', 'distance', 'time']:
                min_val = 0
            else:
                min_val = -10
            
            # Use dimensional analysis or domain knowledge
            max_val = self._estimate_max_value(expr, var)
            
            # Ensure numerical stability
            ranges[var.name] = Range(
                min=min_val,
                max=max_val,
                step=(max_val - min_val) / 100,
                default=(min_val + max_val) / 2
            )
        
        return ranges
    
    def compute_point(
        self, 
        simulation: Simulation, 
        parameters: Dict[str, float]
    ) -> PlotData:
        """
        Compute output for given parameters (called from API).
        """
        try:
            result = simulation.compute_function(**parameters)
            return PlotData(
                success=True,
                data=result,
                message=None
            )
        except (ValueError, ZeroDivisionError) as e:
            return PlotData(
                success=False,
                data=None,
                message=f"Invalid parameters: {str(e)}"
            )
```

#### Visualization Types

1. **Line Plots** - Single variable functions
2. **Scatter Plots** - Discrete data points
3. **Heatmaps** - Two variable functions
4. **Surface Plots** - 3D representations (optional)
5. **Vector Fields** - Direction and magnitude (advanced)

---

### 3.4 Assessment Engine Component

#### Responsibilities
- Generate contextual quiz questions
- Validate user responses
- Provide explanatory feedback
- Track comprehension progress

#### Implementation Details

```python
class AssessmentEngine:
    """
    Generates and evaluates mini-quizzes.
    """
    
    def generate_questions(
        self, 
        equation_analysis: EquationAnalysis,
        num_questions: int = 3
    ) -> List[Question]:
        """
        Generate quiz questions for an equation.
        """
        questions = []
        
        # Question Type 1: Variable relationships
        questions.append(
            self._create_relationship_question(equation_analysis)
        )
        
        # Question Type 2: Prediction
        questions.append(
            self._create_prediction_question(equation_analysis)
        )
        
        # Question Type 3: Conceptual understanding
        questions.append(
            self._create_conceptual_question(equation_analysis)
        )
        
        return questions[:num_questions]
    
    def _create_prediction_question(
        self, 
        analysis: EquationAnalysis
    ) -> Question:
        """
        Ask user to predict outcome of parameter change.
        """
        # Select a variable
        var = random.choice(analysis.variables)
        
        # Generate scenario
        prompt = f"""
        Based on the equation: {analysis.equation.latex}
        
        Create a prediction question:
        - Describe a scenario where {var.name} increases
        - Ask what happens to the output
        - Provide 4 multiple choice options
        - Include detailed explanation
        
        Return as JSON.
        """
        
        response = self.llm_client.complete(prompt)
        question = self._parse_question_response(response)
        
        # Validate with SymPy
        correct_answer = self._verify_answer(
            analysis.sympy_expression,
            var,
            question
        )
        
        question.correct_answer = correct_answer
        
        return question
    
    def evaluate_answer(
        self, 
        question: Question, 
        user_answer: str
    ) -> Feedback:
        """
        Evaluate user's answer and provide feedback.
        """
        is_correct = (user_answer == question.correct_answer)
        
        if is_correct:
            feedback_text = self._generate_positive_feedback(question)
        else:
            feedback_text = self._generate_corrective_feedback(
                question,
                user_answer
            )
        
        return Feedback(
            correct=is_correct,
            explanation=feedback_text,
            hints=self._generate_hints(question) if not is_correct else []
        )
```

---

### 3.5 Summary Generator Component

#### Responsibilities
- Create plain-language summaries
- Generate study notes
- Highlight key takeaways
- Produce downloadable content

#### Implementation Details

```python
class SummaryGenerator:
    """
    Generates summaries and study materials.
    """
    
    def generate_summary(
        self, 
        document: Document,
        analyses: List[EquationAnalysis],
        user_interactions: InteractionLog
    ) -> Summary:
        """
        Create comprehensive summary.
        """
        # Document-level summary
        doc_summary = self._summarize_document(document)
        
        # Key equations summary
        equation_summaries = self._summarize_equations(analyses)
        
        # Personalized insights
        insights = self._generate_insights(
            analyses,
            user_interactions
        )
        
        # Study recommendations
        recommendations = self._generate_recommendations(
            user_interactions
        )
        
        return Summary(
            document_summary=doc_summary,
            key_equations=equation_summaries,
            insights=insights,
            recommendations=recommendations,
            export_formats=['markdown', 'pdf', 'json']
        )
    
    def _summarize_equations(
        self, 
        analyses: List[EquationAnalysis]
    ) -> List[EquationSummary]:
        """
        Create concise summaries for each equation.
        """
        summaries = []
        
        for analysis in analyses:
            prompt = f"""
            Equation: {analysis.equation.latex}
            Context: {analysis.equation.context}
            Variables: {', '.join([v.name for v in analysis.variables])}
            
            Create a 2-3 sentence summary that:
            1. States what the equation represents
            2. Highlights the key relationship
            3. Mentions one practical application
            
            Keep it accessible to undergraduate students.
            """
            
            summary_text = self.llm_client.complete(prompt)
            
            summaries.append(EquationSummary(
                equation=analysis.equation,
                summary=summary_text,
                key_variables=analysis.variables[:3],
                importance_score=self._compute_importance(analysis)
            ))
        
        return summaries
```

---

## 4. Data Models

### 4.1 Core Models

```python
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
import sympy

@dataclass
class Document:
    """Uploaded document representation."""
    id: str
    filename: str
    raw_text: str
    sections: List['Section']
    equations: List['Equation']
    metadata: Dict[str, any]
    created_at: datetime
    
@dataclass
class Section:
    """Document section."""
    title: str
    content: str
    start_position: int
    end_position: int
    section_type: str  # 'introduction', 'methodology', 'results', etc.
    
@dataclass
class Equation:
    """Mathematical equation."""
    id: str
    latex: str
    raw_text: str
    context: str  # Surrounding text
    position: int
    section_id: str
    
@dataclass
class Variable:
    """Equation variable."""
    name: str
    symbol: str
    description: str
    unit: Optional[str]
    variable_type: str  # 'independent', 'dependent', 'constant'
    domain: Optional[tuple]  # Valid range
    
@dataclass
class EquationAnalysis:
    """Complete equation analysis."""
    equation: Equation
    sympy_expression: sympy.Expr
    variables: List[Variable]
    constants: List[Variable]
    steps: List['DerivationStep']
    explanation: str
    complexity_score: float
    
@dataclass
class DerivationStep:
    """Single step in derivation."""
    step_number: int
    expression: str  # LaTeX
    explanation: str
    justification: str
    sympy_expr: sympy.Expr
    
@dataclass
class Simulation:
    """Interactive simulation configuration."""
    id: str
    equation_id: str
    variables: List[Variable]
    ranges: Dict[str, 'Range']
    plot_config: 'PlotConfig'
    compute_function: callable
    
@dataclass
class Range:
    """Variable range for simulation."""
    min: float
    max: float
    step: float
    default: float
    
@dataclass
class PlotConfig:
    """Visualization configuration."""
    plot_type: str  # 'line', 'scatter', 'heatmap', 'surface'
    x_axis: 'AxisConfig'
    y_axis: 'AxisConfig'
    z_axis: Optional['AxisConfig']
    title: str
    annotations: List[str]
    
@dataclass
class Question:
    """Assessment question."""
    id: str
    equation_id: str
    question_text: str
    question_type: str  # 'multiple_choice', 'prediction', 'conceptual'
    options: List[str]
    correct_answer: str
    explanation: str
    difficulty: int  # 1-5
    
@dataclass
class Summary:
    """Document summary."""
    document_id: str
    document_summary: str
    key_equations: List['EquationSummary']
    insights: List[str]
    recommendations: List[str]
    created_at: datetime
```

### 4.2 Database Schema (SQLite for MVP)

```sql
-- Documents
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    raw_text TEXT,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Equations
CREATE TABLE equations (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    latex TEXT NOT NULL,
    context TEXT,
    position INTEGER,
    section_title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Equation Analyses
CREATE TABLE equation_analyses (
    id TEXT PRIMARY KEY,
    equation_id TEXT REFERENCES equations(id),
    variables JSON,
    steps JSON,
    explanation TEXT,
    complexity_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Simulations
CREATE TABLE simulations (
    id TEXT PRIMARY KEY,
    equation_id TEXT REFERENCES equations(id),
    variables JSON,
    ranges JSON,
    plot_config JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Questions
CREATE TABLE questions (
    id TEXT PRIMARY KEY,
    equation_id TEXT REFERENCES equations(id),
    question_text TEXT,
    question_type TEXT,
    options JSON,
    correct_answer TEXT,
    explanation TEXT,
    difficulty INTEGER
);

-- User Sessions
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    interaction_log JSON
);
```

---

## 5. API Design

### 5.1 REST API Endpoints

#### Document Management

```
POST   /api/v1/documents/upload
GET    /api/v1/documents/{document_id}
DELETE /api/v1/documents/{document_id}
GET    /api/v1/documents/{document_id}/sections
```

#### Equation Analysis

```
GET    /api/v1/documents/{document_id}/equations
GET    /api/v1/equations/{equation_id}/analysis
POST   /api/v1/equations/{equation_id}/analyze
```

#### Simulations

```
GET    /api/v1/equations/{equation_id}/simulation
POST   /api/v1/simulations/{simulation_id}/compute
GET    /api/v1/simulations/{simulation_id}/plot-data
```

#### Assessment

```
GET    /api/v1/equations/{equation_id}/questions
POST   /api/v1/questions/{question_id}/submit
GET    /api/v1/questions/{question_id}/feedback
```

#### Summaries

```
GET    /api/v1/documents/{document_id}/summary
POST   /api/v1/documents/{document_id}/summary/export
```

### 5.2 API Specifications

#### Upload Document

```yaml
POST /api/v1/documents/upload

Request:
  Content-Type: multipart/form-data
  Body:
    file: <binary>
    options: {
      "extract_equations": true,
      "auto_analyze": true
    }

Response (202 Accepted):
  {
    "document_id": "doc_abc123",
    "status": "processing",
    "estimated_time": 30,
    "poll_url": "/api/v1/documents/doc_abc123/status"
  }

Response (200 OK) - After Processing:
  {
    "document_id": "doc_abc123",
    "filename": "research_paper.pdf",
    "sections": [...],
    "equations": [
      {
        "id": "eq_001",
        "latex": "E = mc^2",
        "context": "Einstein's mass-energy equivalence...",
        "position": 142
      }
    ],
    "metadata": {
      "page_count": 12,
      "word_count": 3500,
      "equation_count": 15
    }
  }
```

#### Get Equation Analysis

```yaml
GET /api/v1/equations/{equation_id}/analysis

Response (200 OK):
  {
    "equation_id": "eq_001",
    "latex": "E = mc^2",
    "variables": [
      {
        "name": "E",
        "description": "Energy",
        "unit": "joules",
        "type": "dependent"
      },
      {
        "name": "m",
        "description": "Mass",
        "unit": "kilograms",
        "type": "independent"
      },
      {
        "name": "c",
        "description": "Speed of light",
        "unit": "meters per second",
        "type": "constant",
        "value": 299792458
      }
    ],
    "steps": [
      {
        "step_number": 1,
        "expression": "E = mc^2",
        "explanation": "This equation relates energy and mass...",
        "justification": "Derived from special relativity..."
      }
    ],
    "explanation": "Einstein's famous equation shows that...",
    "complexity_score": 0.3
  }
```

#### Compute Simulation Point

```yaml
POST /api/v1/simulations/{simulation_id}/compute

Request:
  {
    "parameters": {
      "m": 1.0,
      "c": 299792458
    }
  }

Response (200 OK):
  {
    "success": true,
    "result": {
      "E": 89875517873681764
    },
    "plot_data": {
      "x": [0, 0.5, 1.0, 1.5, 2.0],
      "y": [0, 4.49e16, 8.99e16, 1.35e17, 1.8e17]
    }
  }

Response (400 Bad Request):
  {
    "success": false,
    "error": "Division by zero",
    "message": "Parameter 'm' cannot be zero"
  }
```

### 5.3 WebSocket Endpoints (Future)

```
WS /api/v1/documents/{document_id}/processing
WS /api/v1/simulations/{simulation_id}/stream
```

---

## 6. Frontend Design

### 6.1 Component Architecture

```
App
├── Layout
│   ├── Header
│   ├── Navigation
│   └── Footer
├── Pages
│   ├── UploadPage
│   ├── DocumentExplorerPage
│   ├── EquationDetailPage
│   ├── SimulationPage
│   └── SummaryPage
└── Components
    ├── DocumentViewer
    ├── EquationRenderer
    ├── InteractivePlot
    ├── StepByStepExplanation
    ├── QuizInterface
    └── SummaryExport
```

### 6.2 Key UI Components

#### Document Explorer

```typescript
interface DocumentExplorerProps {
  documentId: string;
}

const DocumentExplorer: React.FC<DocumentExplorerProps> = ({ documentId }) => {
  const [document, setDocument] = useState<Document | null>(null);
  const [selectedEquation, setSelectedEquation] = useState<string | null>(null);
  
  return (
    <div className="document-explorer">
      <div className="document-pane">
        <DocumentViewer document={document} />
      </div>
      <div className="equation-list">
        {document?.equations.map(eq => (
          <EquationCard
            key={eq.id}
            equation={eq}
            onClick={() => setSelectedEquation(eq.id)}
            selected={selectedEquation === eq.id}
          />
        ))}
      </div>
    </div>
  );
};
```

#### Interactive Simulation

```typescript
interface InteractivePlotProps {
  simulation: Simulation;
  onParameterChange: (params: Parameters) => void;
}

const InteractivePlot: React.FC<InteractivePlotProps> = ({
  simulation,
  onParameterChange
}) => {
  const [parameters, setParameters] = useState(simulation.defaultParameters);
  const [plotData, setPlotData] = useState(null);
  
  const handleSliderChange = (variable: string, value: number) => {
    const newParams = { ...parameters, [variable]: value };
    setParameters(newParams);
    
    // Debounced API call
    debouncedCompute(newParams);
  };
  
  return (
    <div className="interactive-plot">
      <div className="controls">
        {simulation.variables.map(variable => (
          <Slider
            key={variable.name}
            label={variable.description}
            min={simulation.ranges[variable.name].min}
            max={simulation.ranges[variable.name].max}
            step={simulation.ranges[variable.name].step}
            value={parameters[variable.name]}
            onChange={(val) => handleSliderChange(variable.name, val)}
          />
        ))}
      </div>
      <div className="plot-container">
        <Plot
          data={plotData}
          layout={simulation.plotConfig.layout}
          config={{ responsive: true }}
        />
      </div>
    </div>
  );
};
```

### 6.3 State Management

```typescript
// Store structure using Zustand
interface AppState {
  // Document state
  currentDocument: Document | null;
  documents: Document[];
  
  // Equation state
  selectedEquation: Equation | null;
  equationAnalyses: Map<string, EquationAnalysis>;
  
  // Simulation state
  activeSimulation: Simulation | null;
  simulationResults: Map<string, SimulationResult>;
  
  // Quiz state
  currentQuestion: Question | null;
  quizProgress: QuizProgress;
  
  // Actions
  uploadDocument: (file: File) => Promise<void>;
  selectEquation: (equationId: string) => void;
  updateSimulationParams: (params: Parameters) => void;
  submitAnswer: (answer: string) => Promise<Feedback>;
}
```

### 6.4 Responsive Design Breakpoints

```scss
$breakpoint-mobile: 768px;
$breakpoint-tablet: 1024px;
$breakpoint-desktop: 1440px;

// Mobile: Single column, stacked views
// Tablet: Two columns (document + sidebar)
// Desktop: Three columns (document + equations + detail)
```

---

## 7. Processing Pipeline

### 7.1 Document Upload Pipeline

```
┌─────────────┐
│File Upload  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│Validation       │ (Size, format, malware scan)
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│Text Extraction  │ (PDF → Text)
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│Structure        │ (Sections, paragraphs)
│Detection        │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│Equation         │ (LaTeX extraction)
│Extraction       │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│LLM Enhancement  │ (Context, metadata)
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│Storage          │
└─────────────────┘
```

**Estimated Time:** 5-15 seconds for typical document

### 7.2 Equation Analysis Pipeline

```
┌─────────────────┐
│Equation Input   │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│LaTeX → SymPy    │ (Parsing)
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│Variable         │ (Identification)
│Extraction       │
└──────┬──────────┘
       │
       ├────────────────┐
       │                │
       ▼                ▼
┌──────────────┐  ┌─────────────┐
│Step-by-Step  │  │LLM          │
│Derivation    │  │Explanation  │
└──────┬───────┘  └──────┬──────┘
       │                 │
       └────────┬────────┘
                │
                ▼
       ┌────────────────┐
       │Combine Results │
       └────────┬───────┘
                │
                ▼
       ┌────────────────┐
       │Cache & Store   │
       └────────────────┘
```

**Estimated Time:** 3-8 seconds per equation

### 7.3 Simulation Generation Pipeline

```
┌─────────────────────┐
│Equation Analysis    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│Variable Selection   │ (Choose 1-3 key variables)
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│Range Determination  │ (Compute sensible ranges)
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│Function Compilation │ (Create compute function)
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│Initial Data Compute │ (Generate first plot)
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│Plot Config Create   │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│Return to Frontend   │
└─────────────────────┘
```

**Estimated Time:** 2-5 seconds

---

## 8. Security & Performance

### 8.1 Security Measures

#### Input Validation

```python
class SecurityValidator:
    """Validates all user inputs."""
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'.pdf', '.txt'}
    
    def validate_upload(self, file) -> ValidationResult:
        # Check file size
        if file.size > self.MAX_FILE_SIZE:
            return ValidationResult(
                valid=False,
                error="File too large"
            )
        
        # Check extension
        ext = Path(file.filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return ValidationResult(
                valid=False,
                error="Invalid file type"
            )
        
        # Scan for malware (basic check)
        if self._contains_suspicious_content(file):
            return ValidationResult(
                valid=False,
                error="File rejected by security scan"
            )
        
        return ValidationResult(valid=True)
```

#### Code Execution Sandboxing

```python
class SafeExecutor:
    """Safely execute user-influenced code."""
    
    def __init__(self):
        self.timeout = 5  # seconds
        self.memory_limit = 100 * 1024 * 1024  # 100MB
    
    def execute_computation(self, func, params):
        """Execute with timeout and resource limits."""
        
        # Use restricted execution environment
        restricted_globals = {
            '__builtins__': {
                'abs': abs,
                'min': min,
                'max': max,
                # Whitelist only safe built-ins
            },
            'numpy': numpy,
            'math': math,
        }
        
        try:
            # Run with timeout
            result = timeout_wrapper(
                func,
                args=(params,),
                timeout=self.timeout,
                globals=restricted_globals
            )
            return result
        except TimeoutError:
            raise ComputationError("Computation exceeded time limit")
        except MemoryError:
            raise ComputationError("Computation exceeded memory limit")
```

#### API Rate Limiting

```python
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/documents/upload")
@limiter.limit("5/minute")  # 5 uploads per minute
async def upload_document(request: Request, file: UploadFile):
    # Implementation
    pass

@app.post("/api/v1/simulations/{simulation_id}/compute")
@limiter.limit("100/minute")  # 100 computations per minute
async def compute_simulation(request: Request, simulation_id: str):
    # Implementation
    pass
```

### 8.2 Performance Optimization

#### Caching Strategy

```python
from functools import lru_cache
from redis import Redis

class CacheManager:
    """Multi-layer caching."""
    
    def __init__(self):
        self.redis = Redis(host='localhost', port=6379)
        self.ttl_short = 300  # 5 minutes
        self.ttl_long = 3600  # 1 hour
    
    @lru_cache(maxsize=100)
    def get_equation_analysis(self, equation_id: str):
        """In-memory cache for hot data."""
        return self._fetch_from_db(equation_id)
    
    def get_simulation_result(self, simulation_id: str, params: str):
        """Redis cache for computation results."""
        cache_key = f"sim:{simulation_id}:{params}"
        
        # Check cache
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Compute and cache
        result = self._compute_simulation(simulation_id, params)
        self.redis.setex(
            cache_key,
            self.ttl_short,
            json.dumps(result)
        )
        
        return result
```

#### Database Optimization

```sql
-- Indexes for common queries
CREATE INDEX idx_equations_document_id ON equations(document_id);
CREATE INDEX idx_equations_position ON equations(position);
CREATE INDEX idx_analyses_equation_id ON equation_analyses(equation_id);

-- Full-text search for document content
CREATE VIRTUAL TABLE documents_fts USING fts5(
    id,
    raw_text,
    content=documents
);
```

#### Async Processing

```python
from celery import Celery

celery_app = Celery('lattice', broker='redis://localhost:6379')

@celery_app.task
def process_document_async(document_id: str):
    """Background task for heavy processing."""
    
    # Load document
    document = load_document(document_id)
    
    # Extract equations
    equations = extract_equations(document)
    
    # Analyze each equation
    for equation in equations:
        analysis = analyze_equation(equation)
        save_analysis(analysis)
    
    # Generate simulations
    for equation in equations:
        simulation = create_simulation(equation)
        save_simulation(simulation)
    
    # Update status
    update_document_status(document_id, 'completed')
```

### 8.3 Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Document upload | < 2s | File validation and storage |
| Text extraction | < 5s | For 10-page PDF |
| Equation extraction | < 3s | Per document |
| Single equation analysis | < 5s | Including LLM call |
| Simulation creation | < 3s | Initial setup |
| Simulation compute | < 100ms | Per parameter update |
| Page load time | < 1s | Initial render |
| Interactive response | < 200ms | User interactions |

---

## 9. Deployment Strategy

### 9.1 Docker Configuration

```dockerfile
# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# Frontend Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Build application
COPY . .
RUN npm run build

# Production image
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 9.2 Docker Compose

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./lattice.db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LOG_LEVEL=info
    volumes:
      - ./uploads:/app/uploads
      - ./data:/app/data
    depends_on:
      - redis
  
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
  
  celery-worker:
    build: ./backend
    command: celery -A tasks worker --loglevel=info
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - redis
    volumes:
      - ./uploads:/app/uploads
      - ./data:/app/data

volumes:
  redis-data:
```

### 9.3 Environment Configuration

```bash
# .env file
OPENAI_API_KEY=sk-...
DATABASE_URL=sqlite:///./lattice.db
REDIS_URL=redis://localhost:6379
MAX_FILE_SIZE_MB=10
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:3000
```

---

## 10. Testing Strategy

### 10.1 Backend Testing

```python
# tests/test_equation_analyzer.py
import pytest
from lattice.analyzers import EquationAnalyzer

class TestEquationAnalyzer:
    
    @pytest.fixture
    def analyzer(self):
        return EquationAnalyzer(mock_llm_client())
    
    def test_parse_simple_equation(self, analyzer):
        equation = Equation(
            id="test_1",
            latex="E = mc^2",
            context="Energy equation"
        )
        
        analysis = analyzer.analyze(equation)
        
        assert len(analysis.variables) == 3
        assert "E" in [v.name for v in analysis.variables]
        assert analysis.sympy_expression is not None
    
    def test_generate_steps(self, analyzer):
        equation = Equation(
            id="test_2",
            latex="F = ma",
            context="Newton's second law"
        )
        
        analysis = analyzer.analyze(equation)
        
        assert len(analysis.steps) > 0
        assert all(step.explanation for step in analysis.steps)
    
    def test_handle_invalid_latex(self, analyzer):
        equation = Equation(
            id="test_3",
            latex="invalid{{}latex",
            context=""
        )
        
        with pytest.raises(ParseError):
            analyzer.analyze(equation)
```

### 10.2 Frontend Testing

```typescript
// src/components/__tests__/InteractivePlot.test.tsx
import { render, fireEvent, waitFor } from '@testing-library/react';
import InteractivePlot from '../InteractivePlot';

describe('InteractivePlot', () => {
  
  it('renders sliders for each variable', () => {
    const simulation = createMockSimulation();
    const { getByLabelText } = render(
      <InteractivePlot simulation={simulation} />
    );
    
    expect(getByLabelText('Mass (kg)')).toBeInTheDocument();
    expect(getByLabelText('Velocity (m/s)')).toBeInTheDocument();
  });
  
  it('updates plot when slider changes', async () => {
    const simulation = createMockSimulation();
    const { getByLabelText, getByTestId } = render(
      <InteractivePlot simulation={simulation} />
    );
    
    const slider = getByLabelText('Mass (kg)');
    fireEvent.change(slider, { target: { value: '5' } });
    
    await waitFor(() => {
      const plot = getByTestId('plotly-graph');
      expect(plot).toHaveAttribute('data-updated', 'true');
    });
  });
  
  it('handles computation errors gracefully', async () => {
    const simulation = createMockSimulation();
    simulation.computeFunction = () => {
      throw new Error('Division by zero');
    };
    
    const { getByText } = render(
      <InteractivePlot simulation={simulation} />
    );
    
    await waitFor(() => {
      expect(getByText(/error/i)).toBeInTheDocument();
    });
  });
});
```

### 10.3 Integration Testing

```python
# tests/integration/test_full_pipeline.py
import pytest
from pathlib import Path

@pytest.mark.integration
class TestFullPipeline:
    
    def test_document_upload_to_simulation(self, client, test_pdf):
        # Upload document
        response = client.post(
            '/api/v1/documents/upload',
            files={'file': test_pdf}
        )
        assert response.status_code == 202
        document_id = response.json()['document_id']
        
        # Wait for processing
        wait_for_processing(client, document_id)
        
        # Get equations
        response = client.get(f'/api/v1/documents/{document_id}/equations')
        equations = response.json()
        assert len(equations) > 0
        
        equation_id = equations[0]['id']
        
        # Get analysis
        response = client.get(f'/api/v1/equations/{equation_id}/analysis')
        analysis = response.json()
        assert 'variables' in analysis
        
        # Get simulation
        response = client.get(f'/api/v1/equations/{equation_id}/simulation')
        simulation = response.json()
        assert 'variables' in simulation
        
        # Compute point
        response = client.post(
            f'/api/v1/simulations/{simulation["id"]}/compute',
            json={'parameters': {'x': 1.0}}
        )
        assert response.status_code == 200
        assert 'result' in response.json()
```

### 10.4 Test Coverage Goals

- **Unit Tests:** > 80% code coverage
- **Integration Tests:** All major workflows
- **E2E Tests:** Critical user journeys
- **Performance Tests:** All API endpoints

---

## 11. Future Considerations

### 11.1 Phase 2 Features

1. **Cross-Paper Reasoning**
   - Compare equations across multiple documents
   - Identify related concepts and derivations
   - Build knowledge graphs

2. **Advanced OCR**
   - Handwritten equation recognition
   - Diagram and figure analysis
   - Image-based problem solving

3. **Collaborative Features**
   - Real-time multi-user sessions
   - Shared annotations and notes
   - Study groups and discussions

4. **Export Capabilities**
   - Jupyter notebook generation
   - Python script export
   - Interactive HTML reports

5. **Domain-Specific Toolkits**
   - Physics problem solver
   - Machine learning explainer
   - Engineering calculator

### 11.2 Scalability Considerations

#### Database Migration
- Move from SQLite to PostgreSQL
- Implement connection pooling
- Add read replicas for heavy queries

#### Distributed Processing
- Implement message queue (RabbitMQ/Kafka)
- Add worker pools for parallel processing
- Use distributed caching (Redis Cluster)

#### CDN Integration
- Static asset delivery via CDN
- Edge caching for common responses
- Reduced latency for global users

### 11.3 Monitoring & Observability

```python
# Logging configuration
import logging
from pythonjsonlogger import jsonlogger

logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Metrics collection
from prometheus_client import Counter, Histogram

equation_analysis_duration = Histogram(
    'equation_analysis_duration_seconds',
    'Time spent analyzing equations'
)

simulation_compute_count = Counter(
    'simulation_compute_total',
    'Total number of simulation computations'
)
```

### 11.4 Cost Optimization

#### LLM API Costs
- Implement aggressive caching for identical queries
- Use smaller models for simple tasks
- Batch similar requests
- Monitor token usage per feature

#### Infrastructure Costs
- Auto-scaling based on load
- Scheduled scaling (lower capacity during off-hours)
- Spot instances for worker nodes
- Storage tiering (hot/cold data)

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Equation Analysis** | Process of parsing, explaining, and enriching mathematical equations |
| **Derivation Step** | Single transformation in a mathematical derivation |
| **Simulation** | Interactive exploration of equation behavior via parameter manipulation |
| **Assessment** | Quiz or check question to test understanding |
| **Summary** | Plain-language overview of document or concept |

## Appendix B: References

- SymPy Documentation: https://docs.sympy.org
- Plotly.js Documentation: https://plotly.com/javascript/
- FastAPI Documentation: https://fastapi.tiangolo.com/
- React Best Practices: https://react.dev/learn

## Appendix C: Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-12-06 | Initial design document | System |

---

**End of Design Document**
