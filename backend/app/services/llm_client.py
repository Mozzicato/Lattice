import os
import logging
from typing import List, Dict, Any, Optional
import httpx

# Load .env from project root
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM client that uses OpenRouter (free vision models), Groq, or Gemini.
    Priority: OpenRouter (vision) > Groq (text) > Gemini (fallback)
    Includes simple in-memory caching for repeated prompts.
    """
    _cache: dict = {}  # Simple in-memory cache
    _cache_max = 100  # Max cache entries

    def __init__(self):
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")

        # OpenRouter endpoint (OpenAI-compatible)
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        # NVIDIA Nemotron Nano 12B v2 VL - FREE
        self.openrouter_vision_model = "nvidia/nemotron-nano-12b-v2-vl:free"

        # Groq endpoint (text only, fast)
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.groq_model = "llama-3.3-70b-versatile"

        # Gemini endpoint (fallback)
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    async def get_completion(self, messages: List[Dict[str, Any]], temperature: float = 0.7) -> str:
        """
        Get completion from OpenRouter, Groq, or Gemini with caching.
        Messages: [{'role': 'user', 'content': '...', 'images': ['path/to/img']}]
        """
        # Generate cache key from messages
        import hashlib
        cache_key = hashlib.md5(str(messages).encode()).hexdigest()
        
        if cache_key in LLMClient._cache:
            logger.debug(f"Cache hit for prompt")
            return LLMClient._cache[cache_key]
        
        result = None

        # Check for images
        has_images = any(msg.get('images') for msg in messages)

        # For vision tasks, use OpenRouter with NVIDIA Nemotron (FREE, OCR-optimized!)
        if has_images and self.openrouter_key:
            result = await self._openrouter_completion(messages, temperature)
            if result:
                if len(LLMClient._cache) >= LLMClient._cache_max:
                    LLMClient._cache.pop(next(iter(LLMClient._cache)))
                LLMClient._cache[cache_key] = result
                return result

        # For text-only, use Groq (fast)
        if not has_images and self.groq_key:
            result = await self._groq_text_completion(messages, temperature)
            if result:
                if len(LLMClient._cache) >= LLMClient._cache_max:
                    LLMClient._cache.pop(next(iter(LLMClient._cache)))
                LLMClient._cache[cache_key] = result
                return result

        # Fall back to Gemini
        if self.gemini_key:
            result = await self._gemini_completion(messages, temperature)
            if result:
                if len(LLMClient._cache) >= LLMClient._cache_max:
                    LLMClient._cache.pop(next(iter(LLMClient._cache)))
                LLMClient._cache[cache_key] = result
                return result

        logger.error("No LLM API key available")
        return "Error: No LLM API configured. Please set OPENROUTER_API_KEY for vision tasks."

    async def _openrouter_completion(self, messages: List[Dict[str, Any]], temperature: float) -> Optional[str]:
        """Call OpenRouter API with NVIDIA Nemotron for vision/OCR tasks."""
        import base64
        import pathlib
        
        try:
            # Build messages in OpenAI vision format
            formatted_messages = []
            
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                images = msg.get('images', [])
                
                if images:
                    # Vision format: content is a list of parts
                    content_parts = []
                    
                    # Add text content first
                    if content:
                        content_parts.append({"type": "text", "text": content})
                    
                    # Add images as base64
                    for img_path in images:
                        path = pathlib.Path(img_path)
                        if path.exists():
                            mime_type = "image/png"
                            if path.suffix.lower() in ['.jpg', '.jpeg']:
                                mime_type = "image/jpeg"
                            
                            with open(path, "rb") as f:
                                img_data = base64.b64encode(f.read()).decode("utf-8")
                            
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{img_data}"
                                }
                            })
                    
                    formatted_messages.append({"role": role, "content": content_parts})
                else:
                    formatted_messages.append({"role": role, "content": content})
            
            logger.info(f"Calling OpenRouter with model: {self.openrouter_vision_model}")
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    self.openrouter_url,
                    headers={
                        "Authorization": f"Bearer {self.openrouter_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://lattice-app.local",
                        "X-Title": "Lattice Note Beautifier"
                    },
                    json={
                        "model": self.openrouter_vision_model,
                        "messages": formatted_messages,
                        "temperature": temperature,
                        "max_tokens": 4096
                    }
                )
            
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.warning(f"OpenRouter API error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            logger.warning(f"OpenRouter API call failed: {e}")
            return None

    async def _groq_text_completion(self, messages: List[Dict[str, str]], temperature: float) -> Optional[str]:
        """Call Groq API for text-only tasks."""
        try:
            clean_messages = [{'role': m['role'], 'content': m['content']} for m in messages]
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.groq_url,
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.groq_model,
                        "messages": clean_messages,
                        "temperature": temperature,
                        "max_tokens": 4096
                    }
                )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.warning(f"Groq API error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            logger.warning(f"Groq API call failed: {e}")
            return None

    async def _groq_completion(self, messages: List[Dict[str, Any]], temperature: float, has_images: bool = False) -> Optional[str]:
        """Call Groq API (OpenAI-compatible). Supports vision with llama-3.2-90b-vision-preview."""
        import base64
        import pathlib
        
        try:
            model = self.groq_vision_model if has_images else self.groq_model
            
            # Build messages in OpenAI format
            formatted_messages = []
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                images = msg.get('images', [])
                
                if images and has_images:
                    # Vision format: content is a list of parts
                    content_parts = []
                    
                    # Add text content first
                    if content:
                        content_parts.append({"type": "text", "text": content})
                    
                    # Add images as base64
                    for img_path in images:
                        path = pathlib.Path(img_path)
                        if path.exists():
                            mime_type = "image/png"
                            if path.suffix.lower() in ['.jpg', '.jpeg']:
                                mime_type = "image/jpeg"
                            
                            with open(path, "rb") as f:
                                img_data = base64.b64encode(f.read()).decode("utf-8")
                            
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{img_data}"
                                }
                            })
                    
                    formatted_messages.append({"role": role, "content": content_parts})
                else:
                    formatted_messages.append({"role": role, "content": content})
            
            async with httpx.AsyncClient(timeout=120.0) as client:  # Longer timeout for vision
                resp = await client.post(
                    self.groq_url,
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": formatted_messages,
                        "temperature": temperature,
                        "max_tokens": 4096  # More tokens for full page transcription
                    }
                )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.warning(f"Groq API error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            logger.warning(f"Groq API call failed: {e}")
            return None

    async def _gemini_completion(self, messages: List[Dict[str, Any]], temperature: float) -> Optional[str]:
        """Call Gemini API. Supports images."""
        import base64
        import pathlib

        try:
            # Convert messages to Gemini format
            contents = []
            
            # Combine all messages into a single prompt for Gemini multi-turn or single-turn structure
            # But the REST API expects "contents" list.
            
            for msg in messages:
                role = "user" if msg.get("role") == "user" else "model"
                if msg.get("role") == "system":
                    # prepend system prompt to next user message or handle separately
                    # Gemini REST doesn't have strict 'system' role in 'contents' usually, 
                    # but we can try to just make it user or prepend.
                    # Best practice for simple REST: Prepend textual instruction.
                    continue
                
                parts = []
                content_text = msg.get("content", "")
                
                # Check for system prompt in previous messages to prepend
                if msg.get("role") == "user":
                    system_prompts = [m["content"] for m in messages if m.get("role") == "system"]
                    if system_prompts:
                        content_text = "\n".join(system_prompts) + "\n\n" + content_text

                parts.append({"text": content_text})

                # Handle images
                images = msg.get("images", [])
                for img_path in images:
                    path = pathlib.Path(img_path)
                    if path.exists():
                        mime_type = "image/png"  # Default
                        if path.suffix.lower() in ['.jpg', '.jpeg']:
                            mime_type = "image/jpeg"
                        
                        with open(path, "rb") as f:
                            img_data = base64.b64encode(f.read()).decode("utf-8")
                        
                        parts.append({
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": img_data
                            }
                        })
                
                contents.append({
                    "role": role,
                    "parts": parts
                })

            # If no contents (e.g. only system message), make a dummy user message
            if not contents:
                return None

            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 4096  # Increased for full page text
                }
            }

            url = f"{self.gemini_url}?key={self.gemini_key}"
            async with httpx.AsyncClient(timeout=60.0) as client: # Increased timeout for images
                resp = await client.post(url, json=payload)

            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return None
            else:
                logger.warning(f"Gemini API error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}")
            return None

    async def get_structured_completion(self, messages: List[Dict[str, str]], schema: Any) -> Dict[str, Any]:
        """
        Get structured JSON output. Falls back to parsing the text response.
        """
        import json
        # Append instruction to return JSON
        messages = messages.copy()
        messages.append({"role": "user", "content": "Return your response as valid JSON only, no markdown."})

        text = await self.get_completion(messages, temperature=0.3)
        try:
            # Try to extract JSON from the response
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except Exception:
            return {"raw": text}

    def complete(self, prompt: str, temperature: float = 0.7, max_tokens: int = 512) -> str:
        """Synchronous wrapper for simple prompt completion (used by document_processor)."""
        import asyncio
        messages = [{"role": "user", "content": prompt}]
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, create a new task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.get_completion(messages, temperature))
                    return future.result(timeout=60)
            else:
                return loop.run_until_complete(self.get_completion(messages, temperature))
        except Exception as e:
            logger.error(f"Sync completion failed: {e}")
            return f"Error: {e}"

    async def generate_response(self, prompt: str) -> str:
        """Simple async prompt -> response helper."""
        return await self.get_completion([{"role": "user", "content": prompt}])
