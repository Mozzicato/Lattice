from typing import List, Dict
from .llm_client import LLMClient

class SocraticTutor:
    def __init__(self):
        self.llm = LLMClient()
        self.system_prompt = """
You are Lattice, a Socratic Tutor. Your goal is to help the user understand concepts deeply by asking guiding questions, not by giving direct answers.

Guidelines:
1.  **Never give the answer directly.** Instead, ask a question that leads the user one step closer.
2.  **Check understanding.** Before moving to the next concept, ensure the user grasps the current one.
3.  **Be encouraging but rigorous.** Celebrate progress, but don't let misconceptions slide.
4.  **Use analogies.** If the user is stuck, offer a simple analogy.
5.  **Structure before Math.** Explain the *why* and *how* before diving into formulas.

If the user says "I'm lost", switch to a simpler, more intuitive explanation style.
"""

    async def generate_response(self, history: List[Dict[str, str]], context: str = "") -> str:
        """
        Generates a Socratic response based on the conversation history and document context.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        
        if context:
            messages.append({"role": "system", "content": f"Context from document:\n{context}"})
            
        messages.extend(history)
        
        response = await self.llm.get_completion(messages)
        return response
