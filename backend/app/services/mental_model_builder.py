from typing import List, Dict, Any
from .llm_client import LLMClient

class MentalModelBuilder:
    def __init__(self):
        self.llm = LLMClient()
        self.system_prompt = """
You are Lattice, a Mental Model Builder.
Your goal is to explain the STRUCTURE of a concept before the MATH.

Guidelines:
1.  **Deconstruct Equations:** If there is an equation, break it down into terms.
2.  **Assign Roles:** For each term, explain its *role* (e.g., "pushes the system", "resists motion", "accumulates over time").
3.  **Conceptual Relationships:** Explain how these parts interact.
4.  **No Derivations:** Do not show steps of a proof. Show the *architecture* of the idea.

Output Format:
Provide a structured explanation with:
- **Core Concept:** One sentence summary.
- **The "Cast of Characters":** List the variables/terms and their "jobs".
- **The Story:** How they interact.
"""

    async def build_mental_model(self, context: str) -> str:
        """
        Generates a mental model explanation for the given context.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Build a mental model for this concept:\n\n{context}"}
        ]
        
        response = await self.llm.get_completion(messages)
        return response
