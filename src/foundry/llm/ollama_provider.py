"""Ollama provider for local Qwen models."""

import asyncio
import enum
from typing import Optional, List, Any, AsyncIterator
import logging
import httpx
from foundry.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from foundry.config import settings



logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama provider for local model inference."""
    
    # Class-level semaphore to prevent VRAM exhaustion on local hardware (Req 8.4)
    _semaphore = asyncio.Semaphore(1)
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Initialize Ollama provider.
        
        Args:
            model_name: Model name (defaults to config)
            base_url: Ollama server base URL (defaults to config)
            **kwargs: Additional configuration
        """
        super().__init__(
            model_name=model_name or settings.ollama_model_name,
            **kwargs
        )
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)
        )
    
    async def _check_connection(self):
        """Verify connection to Ollama server."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Could not connect to Ollama at {self.base_url}. "
                "Please ensure Ollama is running (e.g., 'ollama serve')."
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ConnectionError(
                    f"Ollama API endpoint not found at {self.base_url}. "
                    "Make sure you are using a recent version of Ollama."
                )
        except Exception as e:
             raise ConnectionError(f"Ollama connection check failed: {str(e)}")
    
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate completion from messages.
        
        Args:
            messages: List of conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse with generated content
        """
        # Convert messages to Ollama format
        ollama_messages = [
            {"role": msg.role, "content": msg.content} 
            for msg in messages
        ]
        
        payload = {
            "model": self.model_name,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 8192,  # Increased for larger projects
                "num_thread": 4,  # More stable default
                "num_predict": 2048, # Prevent runaway generation
            }
        }
        
        if json_mode:
            payload["format"] = "json"
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        payload["options"].update(kwargs)
        
        # Proactive connection check
        try:
            await self._check_connection()
        except ConnectionError as e:
            # Re-raise as a clean error message, or log a warning
            print(f"Error: {e}")
            raise

        try:
            async with self._semaphore:
                logger.info(f"LLM Request starting (Model: {self.model_name}, Payload: {len(str(payload))} chars)")
                response = await asyncio.wait_for(
                    self.client.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                    ),
                    timeout=120.0,
                )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Ollama request timed out after 120s for model {self.model_name}"
            )
        if response.status_code == 404:
             raise ConnectionError(f"Model '{self.model_name}' not found in Ollama. Please run 'ollama pull {self.model_name}'")
        response.raise_for_status()
        
        data = response.json()
        
        # Extract token counts from response
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        total_tokens = prompt_tokens + completion_tokens
        
        return LLMResponse(
            content=data["message"]["content"],
            model=data.get("model", self.model_name),
            tokens_used=total_tokens,
            finish_reason=data.get("done_reason", "stop"),
            metadata={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_duration": data.get("total_duration", 0),
                "load_duration": data.get("load_duration", 0),
                "prompt_eval_duration": data.get("prompt_eval_duration", 0),
                "eval_duration": data.get("eval_duration", 0),
            }
        )
    
    async def stream_generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> AsyncIterator[str]:
        """Stream completion from messages.
        
        Args:
            messages: List of conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Yields:
            Chunks of generated content
        """
        # Convert messages to Ollama format
        ollama_messages = [
            {"role": msg.role, "content": msg.content} 
            for msg in messages
        ]
        
        payload = {
            "model": self.model_name,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": temperature,
            }
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        payload["options"].update(kwargs)
        
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        import json
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            content = data["message"]["content"]
                            if content:
                                yield content
                        
                        # Check if done
                        if data.get("done", False):
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "ollama"
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
