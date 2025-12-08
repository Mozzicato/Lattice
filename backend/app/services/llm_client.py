"""
LLM Client - Unified interface for OpenAI and Gemini
"""
import logging
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM client supporting OpenAI and Gemini.
    """
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
        
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the appropriate LLM client"""
        if self.provider == "gemini":
            if not settings.GEMINI_API_KEY:
                logger.warning("Gemini API key not found. LLM features will be limited.")
                return
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.client = genai.GenerativeModel(self.model)
                logger.info(f"Initialized Gemini client with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None
                
        elif self.provider == "openai":
            if not settings.OPENAI_API_KEY:
                logger.warning("OpenAI API key not found. LLM features will be limited.")
                return
            
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info(f"Initialized OpenAI client with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            logger.error(f"Unknown LLM provider: {self.provider}")
    
    def is_available(self) -> bool:
        """Check if LLM client is available"""
        return self.client is not None
    
    def complete(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Optional[str]:
        """
        Generate completion from prompt.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            Generated text or None if unavailable
        """
        if not self.is_available():
            logger.warning("LLM client not available")
            return None
        
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        try:
            if self.provider == "gemini":
                return self._complete_gemini(prompt, system_prompt, temp, max_tok)
            elif self.provider == "openai":
                return self._complete_openai(prompt, system_prompt, temp, max_tok)
        except Exception as e:
            logger.error(f"LLM completion failed: {e}", exc_info=True)
            return None
    
    def _complete_gemini(
        self, 
        prompt: str, 
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int = None
    ) -> str:
        """Complete using Gemini"""
        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        # Configure generation
        generation_config = {
            "temperature": temperature,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": max_tokens if max_tokens else self.max_tokens,
        }
        
        response = self.client.generate_content(
            full_prompt,
            generation_config=generation_config
        )
        
        # Handle blocked or empty responses
        if not response or not response.text:
            logger.warning("Gemini returned empty response")
            return ""
        
        return response.text
    
    def _complete_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Complete using OpenAI"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content
    
    def generate_equation_explanation(
        self, 
        latex: str, 
        variables: list,
        context: str = ""
    ) -> str:
        """
        Generate explanation for an equation.
        
        Args:
            latex: LaTeX equation
            variables: List of variable dicts
            context: Surrounding context
            
        Returns:
            Explanation text
        """
        if not self.is_available():
            return self._fallback_explanation(latex, variables)
        
        var_descriptions = ", ".join([
            f"{v['name']} ({v['description']})" for v in variables
        ])
        
        system_prompt = """You are a patient mathematics tutor explaining equations to undergraduate students.
Provide clear, intuitive explanations avoiding unnecessary jargon."""
        
        prompt = f"""Explain this equation in 2-3 sentences:

Equation: {latex}
Variables: {var_descriptions}
Context: {context if context else 'No additional context'}

Provide:
1. An intuitive one-sentence explanation
2. The key relationship it describes
3. A practical application or example if applicable

Keep it accessible and concise."""
        
        explanation = self.complete(prompt, system_prompt, temperature=0.7)
        
        if explanation:
            return explanation
        else:
            return self._fallback_explanation(latex, variables)
    
    def _fallback_explanation(self, latex: str, variables: list) -> str:
        """Generate basic explanation without LLM"""
        var_names = [v['description'] for v in variables]
        
        if len(var_names) == 0:
            return f"This equation: {latex}"
        elif len(var_names) == 1:
            return f"This equation describes {var_names[0]}."
        elif len(var_names) == 2:
            return f"This equation shows the relationship between {var_names[0]} and {var_names[1]}."
        else:
            return f"This equation relates {', '.join(var_names[:-1])}, and {var_names[-1]}."


# Global LLM client instance
_llm_client = None

def get_llm_client() -> LLMClient:
    """Get or create global LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
