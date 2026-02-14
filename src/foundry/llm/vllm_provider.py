"""vLLM provider for local Qwen models."""

from typing import Optional, List, Any, AsyncIterator
import httpx
from foundry.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from foundry.config import settings


class VLLMProvider(BaseLLMProvider):
    """vLLM provider for local model inference."""
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Initialize vLLM provider.
        
        Args:
            model_name: Model name (defaults to config)
            base_url: vLLM server base URL (defaults to config)
            api_key: API key for vLLM server (defaults to config)
            **kwargs: Additional configuration
        """
        super().__init__(
            model_name=model_name or settings.vllm_model_name,
            **kwargs
        )
        self.base_url = (base_url or settings.vllm_base_url).rstrip("/")
        self.api_key = api_key or settings.vllm_api_key
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
        payload = {
            "model": self.model_name,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "temperature": temperature,
            "stream": False,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        payload.update(kwargs)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        
        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model_name),
            tokens_used=usage.get("total_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
            metadata={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
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
        payload = {
            "model": self.model_name,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "temperature": temperature,
            "stream": True,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        payload.update(kwargs)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with self.client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    
                    try:
                        import json
                        data = json.loads(data_str)
                        delta = data["choices"][0]["delta"]
                        if "content" in delta:
                            yield delta["content"]
                    except (json.JSONDecodeError, KeyError):
                        continue
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "vllm"
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
