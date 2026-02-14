"""Base LLM provider interface."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class LLMMessage:
    """Message for LLM conversation."""
    role: str  # system, user, assistant
    content: str


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    model: str
    tokens_used: int
    finish_reason: str
    metadata: Dict[str, Any]


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model_name: str, **kwargs: Any) -> None:
        """Initialize LLM provider.
        
        Args:
            model_name: Name of the model to use
            **kwargs: Additional provider-specific configuration
        """
        self.model_name = model_name
        self.config = kwargs
    
    @abstractmethod
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
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional generation parameters
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def stream_generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ):
        """Stream completion from messages.
        
        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional generation parameters
            
        Yields:
            Chunks of generated content
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name."""
        pass
