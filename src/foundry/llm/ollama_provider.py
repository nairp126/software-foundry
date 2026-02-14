"""Ollama provider for local Qwen models."""

from typing import Optional, List, Any, AsyncIterator
import httpx
from foundry.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from foundry.config import settings


class OllamaProvider(BaseLLMProvider):
    """Ollama provider for local model inference."""
    
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
        self.client = httpx.AsyncClient(timeout=300.0)
    
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
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
            }
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        payload["options"].update(kwargs)
        
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
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
