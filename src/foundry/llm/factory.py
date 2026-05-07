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
        """Create LLM provider instance with optional failover."""
        primary_name = provider_name or settings.default_llm_provider
        
        if settings.enable_provider_failover:
            from foundry.llm.failover_provider import FailoverLLMProvider
            
            providers = []
            # Primary provider
            providers.append(LLMProviderFactory._get_single_provider(primary_name, model_name, **kwargs))
            
            # Backup: fallback to OpenAI if not primary and key is available
            if primary_name != "openai" and settings.openai_api_key:
                providers.append(OpenAIProvider(model_name=settings.openai_model_name))
                
            # Backup: fallback to Ollama if not primary
            if primary_name != "ollama":
                providers.append(OllamaProvider(model_name=settings.ollama_model_name))
                
            return FailoverLLMProvider(providers)
            
        return LLMProviderFactory._get_single_provider(primary_name, model_name, **kwargs)

    @staticmethod
    def _get_single_provider(
        provider: str,
        model_name: Optional[str] = None,
        **kwargs
    ) -> BaseLLMProvider:
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
