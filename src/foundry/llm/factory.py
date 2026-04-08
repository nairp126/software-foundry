"""LLM provider factory."""

from typing import Optional
from foundry.llm.base import BaseLLMProvider
from foundry.llm.vllm_provider import VLLMProvider
from foundry.llm.ollama_provider import OllamaProvider
from foundry.llm.openai_provider import OpenAIProvider
from foundry.llm.anthropic_provider import AnthropicProvider
from foundry.config import settings


class LLMProviderFactory:
    """Factory for creating LLM providers."""
    
    @staticmethod
    def create_provider(
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        **kwargs
    ) -> BaseLLMProvider:
        """Create LLM provider instance.
        
        Args:
            provider_name: Provider name (ollama, vllm, openai, anthropic)
            model_name: Model name to use
            **kwargs: Additional provider-specific configuration
            
        Returns:
            BaseLLMProvider instance
            
        Raises:
            ValueError: If provider is not supported
        """
        provider = provider_name or settings.default_llm_provider
        
        if provider == "ollama":
            return OllamaProvider(model_name=model_name, **kwargs)
        elif provider == "vllm":
            return VLLMProvider(model_name=model_name, **kwargs)
        elif provider == "openai":
            return OpenAIProvider(model_name=model_name, **kwargs)
        elif provider == "anthropic":
            return AnthropicProvider(model_name=model_name, **kwargs)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    @staticmethod
    def get_default_provider() -> BaseLLMProvider:
        """Get default LLM provider from configuration.
        
        Returns:
            BaseLLMProvider instance
        """
        return LLMProviderFactory.create_provider()
