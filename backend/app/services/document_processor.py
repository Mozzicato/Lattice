"""
Comprehensive Document Processor
Extracts ALL content from ALL pages before starting the learning process
"""
import logging
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from app.services.document_parser import DocumentParser, PageContent
from app.services.equation_extractor import EquationExtractor, ExtractedEquation
from app.services.equation_analyzer import EquationAnalyzer
from app.services.llm_client import LLMClient
from app.services.ocr_engine import OcrEngine
from app.config import settings
from app.models import Document, Equation, EquationAnalysis

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Comprehensive processor that scans ENTIRE document page by page and extracts:
    - Full text content from ALL pages
    - ALL images from ALL pages
    - All equations with context
    - Key concepts and terminology
    - Section structure
    - Generated analyses for all equations
    """
    
    def __init__(self, llm_client: LLMClient):
        self.parser = DocumentParser()
        self.equation_extractor = EquationExtractor()
        self.equation_analyzer = EquationAnalyzer(llm_client=llm_client)
        self.ocr_engine = OcrEngine(low_confidence_threshold=settings.OCR_LOW_CONFIDENCE)
        self.llm_client = llm_client
    
    def process_document(
        self,
        file_path: str,
        document: Document,
        db: Session
    ) -> Dict[str, Any]:
        """
        Process ENTIRE document page by page and extract ALL content
        
        Args:
            file_path: Path to uploaded file
            document: Document model instance
            db: Database session
            
        Returns:
            Processing results summary
        """
        logger.info(f"Starting comprehensive document processing for {document.id}")
        
        results = {
            "document_id": document.id,
            "status": "processing",
            "total_pages": 0,
            "pages_processed": 0,
            "equations_found": 0,
            "equations_analyzed": 0,
            "images_extracted": 0,
            "concepts_extracted": 0,
            "sections_identified": 0,
            "ocr_pages": 0,
            "ocr_low_confidence_pages": 0,
            "ocr_low_confidence_segments": 0,
            "errors": []
        }
        
        try:
            # Step 1: Get page count first
            page_count = self.parser.get_page_count(file_path)
            results["total_pages"] = page_count
            logger.info(f"Step 1: Document has {page_count} pages")
            
            # Step 2: Extract ALL pages with images
            logger.info("Step 2: Extracting ALL pages with images...")
            all_pages = self.parser.extract_all_pages(file_path, document.id, save_snapshots=True)
            results["pages_processed"] = len(all_pages)
            
            # Collect all text and images
            all_text_parts = []
            all_images = []
            page_texts: Dict[int, str] = {}  # page_num -> text
            page_snapshots: List[Dict[str, Any]] = []
            ocr_results: Dict[int, Any] = {}
            
            for page in all_pages:
                if page.snapshot_path:
                    page_snapshots.append({"page": page.page_num, "path": page.snapshot_path})
                
                ocr_result = None
                if page.snapshot_path:
                    ocr_result = self.ocr_engine.extract_text(page.snapshot_path)
                    if ocr_result:
                        ocr_results[page.page_num] = ocr_result
                        results["ocr_pages"] += 1
                        if ocr_result.get("low_confidence_segments"):
                            results["ocr_low_confidence_pages"] += 1
                
                text_choice = page.text or ""
                if ocr_result and ocr_result.get("text"):
                    ocr_text = ocr_result.get("text", "")
                    if not text_choice or len(ocr_text) > len(text_choice):
                        text_choice = ocr_text
                
                all_text_parts.append(f"\n\n=== PAGE {page.page_num} ===\n\n")
                all_text_parts.append(text_choice)
                page_texts[page.page_num] = text_choice
                
                for img in page.images:
                    all_images.append(img)
                    results["images_extracted"] += 1
            
            raw_text = "".join(all_text_parts)
            document.raw_text = raw_text
            
            logger.info(f"  Total text: {len(raw_text)} characters from {len(all_pages)} pages")
            logger.info(f"  Total images: {results['images_extracted']}")
            logger.info(f"  OCR pages: {results['ocr_pages']} (low-confidence pages: {results['ocr_low_confidence_pages']})")
            results["ocr_low_confidence_segments"] = sum(
                len(v.get("low_confidence_segments", [])) for v in ocr_results.values()
            )
            results["ocr_low_confidence_segments"] = sum(
                len(v.get("low_confidence_segments", [])) for v in ocr_results.values()
            )
            
            # Step 3: Extract ALL equations with context
            logger.info("Step 3: Extracting all equations...")
            extracted_equations = self.equation_extractor.extract_equations(raw_text)
            results["equations_found"] = len(extracted_equations)
            
            # Step 4: Save equations to database
            logger.info("Step 4: Saving equations to database...")
            equation_models = []
            for eq in extracted_equations:
                # Identify section for this equation
                section = self.equation_extractor.identify_section(raw_text, eq.position)
                
                equation_model = Equation(
                    document_id=document.id,
                    latex=eq.latex,
                    context=eq.context,
                    position=eq.position,
                    section_title=section
                )
                db.add(equation_model)
                equation_models.append(equation_model)
            
            db.flush()  # Get IDs for equations
            
            # Step 5: Analyze equations upfront (batch processing, limit to first 20)
            logger.info("Step 5: Analyzing equations with LLM...")
            analyzed_count = 0
            
            for equation_model in equation_models[:20]:  # Limit to prevent timeout
                try:
                    # Parse equation
                    parsed = self.equation_analyzer.parse_to_sympy(equation_model.latex)
                    
                    if parsed:
                        # Generate AI explanation
                        analysis_result = self.equation_analyzer.analyze_equation(
                            equation_model.latex,
                            context=equation_model.context
                        )
                        
                        if not analysis_result.get('success'):
                            continue
                            
                        explanation = analysis_result['explanation']
                        variables = analysis_result['variables']
                        
                        # Calculate complexity
                        complexity = self._calculate_complexity(parsed, variables)
                        
                        # Save analysis
                        analysis = EquationAnalysis(
                            equation_id=equation_model.id,
                            variables=variables,
                            steps=[],
                            explanation=explanation,
                            complexity_score=complexity
                        )
                        db.add(analysis)
                        analyzed_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to analyze equation {equation_model.id}: {e}")
            
            results["equations_analyzed"] = analyzed_count
            
            # Step 6: Extract key concepts from entire document
            logger.info("Step 6: Extracting key concepts...")
            concepts = self._extract_concepts(raw_text, extracted_equations)
            results["concepts_extracted"] = len(concepts)
            
            # Step 7: Identify document structure
            logger.info("Step 7: Identifying document structure...")
            sections = self._identify_sections(raw_text)
            results["sections_identified"] = len(sections)
            
            # Update document metadata with EVERYTHING
            document.doc_metadata = {
                "page_count": page_count,
                "pages_processed": len(all_pages),
                "equation_count": results["equations_found"],
                "image_count": results["images_extracted"],
                "character_count": len(raw_text),
                "status": "ready_for_learning",
                "concepts": concepts,
                "sections": sections,
                "images": all_images,  # Store all image info
                "page_texts": page_texts,  # Store text per page
                "page_snapshots": page_snapshots,  # Store snapshot paths per page
                "ocr_results": ocr_results,  # Store OCR results per page
                "ocr_low_confidence_segments": results["ocr_low_confidence_segments"],
                "processing_complete": True
            }
            
            db.commit()
            results["status"] = "completed"
            
            logger.info(f"Document processing completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}", exc_info=True)
            db.rollback()
            results["status"] = "failed"
            results["errors"].append({"error": str(e)})
            return results
    
    def _extract_concepts(
        self,
        text: str,
        equations: List[ExtractedEquation]
    ) -> List[Dict[str, str]]:
        """
        Extract key concepts and terminology from the document
        """
        try:
            # Build prompt for concept extraction
            equation_list = "\n".join([f"- {eq.latex}" for eq in equations[:10]])  # Limit to first 10
            
            prompt = f"""Analyze this educational content and extract the key concepts and terminology.

Document excerpt (first 2000 chars):
{text[:2000]}

Equations found:
{equation_list}

List the 5-10 most important concepts or terms that a student should understand.
Return as a JSON array with format: [{{"term": "concept name", "definition": "brief definition"}}]

Focus on: physics/math concepts, variables, fundamental principles.
"""
            
            response = self.llm_client.complete(prompt, temperature=0.3, max_tokens=800)
            
            # Parse JSON response (basic parsing, could be improved)
            import json
            try:
                concepts = json.loads(response)
                return concepts if isinstance(concepts, list) else []
            except:
                # Fallback: extract simple concepts from section titles
                return self._extract_concepts_fallback(text)
                
        except Exception as e:
            logger.warning(f"Concept extraction failed: {e}")
            return self._extract_concepts_fallback(text)
    
    def _extract_concepts_fallback(self, text: str) -> List[Dict[str, str]]:
        """Fallback concept extraction without LLM"""
        concepts = []
        
        # Look for common physics/math terms
        common_terms = [
            ("Force", "Physical quantity that causes an object to accelerate"),
            ("Energy", "Capacity to do work"),
            ("Velocity", "Rate of change of position"),
            ("Acceleration", "Rate of change of velocity"),
            ("Mass", "Measure of matter in an object"),
        ]
        
        for term, definition in common_terms:
            if term.lower() in text.lower():
                concepts.append({"term": term, "definition": definition})
        
        return concepts[:5]
    
    def _identify_sections(self, text: str) -> List[Dict[str, Any]]:
        """
        Identify document structure (chapters, sections, subsections)
        """
        sections = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Markdown headers
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                sections.append({
                    "level": level,
                    "title": title,
                    "line": i
                })
            
            # Numbered sections (e.g., "1. Introduction", "1.1 Background")
            elif line and line[0].isdigit() and '.' in line[:10]:
                sections.append({
                    "level": line.count('.'),
                    "title": line,
                    "line": i
                })
        
        return sections
    
    def _calculate_complexity(self, expr, variables: List[Dict]) -> float:
        """Calculate equation complexity score (0-1)"""
        complexity = 0.0
        
        # Factor 1: Number of variables (0-0.3)
        complexity += min(len(variables) * 0.05, 0.3)
        
        # Factor 2: Expression depth (0-0.4)
        try:
            from sympy import count_ops
            ops_count = count_ops(expr)
            complexity += min(ops_count * 0.04, 0.4)
        except:
            pass
        
        # Factor 3: Special functions (0-0.3)
        expr_str = str(expr)
        special_funcs = ['sin', 'cos', 'tan', 'exp', 'log', 'sqrt', 'integral', 'derivative']
        func_count = sum(1 for func in special_funcs if func in expr_str.lower())
        complexity += min(func_count * 0.1, 0.3)
        
        return min(complexity, 1.0)
