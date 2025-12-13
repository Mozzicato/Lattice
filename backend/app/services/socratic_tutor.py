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
        self.simplification_prompt = """
You are Lattice, in "I'm Lost" mode. The user is overwhelmed.
Your goal is to explain the current concept using PURE INTUITION and ANALOGIES.

Guidelines:
1.  **NO MATH.** Do not use formulas or complex notation.
2.  **Use Analogies.** Relate the concept to everyday physical objects (water, gravity, traffic, etc.).
3.  **Step Back.** Go up one level of abstraction. Explain the "Big Idea".
4.  **Be Calm.** Use reassuring language.
5.  **Short & Clear.** Keep it brief.

After explaining, ask a simple checking question to see if they are back on track.
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

    async def generate_simplified_explanation(self, history: List[Dict[str, str]], context: str = "") -> str:
        """
        Generates a simplified explanation (I'm Lost mode).
        """
        messages = [{"role": "system", "content": self.simplification_prompt}]
        
        if context:
            messages.append({"role": "system", "content": f"Context from document:\n{context}"})
            
        messages.extend(history)
        # Add an explicit instruction to the end to trigger the simplification
        messages.append({"role": "user", "content": "I'm lost. Please explain this differently, without the math."})
        
        response = await self.llm.get_completion(messages)
        return response
