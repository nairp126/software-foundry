"""Provider failover implementation for patent-grade reliability."""

import logging
import asyncio
from typing import List, Optional, Any, AsyncGenerator
from foundry.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from foundry.config import settings

logger = logging.getLogger(__name__)

class FailoverLLMProvider(BaseLLMProvider):
    """
    PATENT-CRITICAL: Reliable Multi-Provider Failover.
    Automatically switches to backup providers if the primary fails.
    This strengthens the 'high-availability orchestration' patent claim.
    """
    
    def __init__(self, providers: List[BaseLLMProvider]):
        if not providers:
            raise ValueError("FailoverProvider requires at least one provider.")
        self.providers = providers
        super().__init__(model_name=providers[0].model_name)

    @property
    def provider_name(self) -> str:
        return f"failover({','.join([p.provider_name for p in self.providers])})"

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        last_error = None
        for i, provider in enumerate(self.providers):
            try:
                if i > 0:
                    logger.warning(f"Failover triggered. Using backup provider {i}: {provider.provider_name}")
                return await provider.generate(messages, temperature=temperature, max_tokens=max_tokens, **kwargs)
            except Exception as e:
                last_error = e
                logger.error(f"Provider {i} ({provider.provider_name}) failed: {e}")
                if i == len(self.providers) - 1:
                    break
                # Only wait if failover delay is configured
                if settings.provider_failover_retry_delay > 0:
                    await asyncio.sleep(settings.provider_failover_retry_delay)
        
        if last_error:
            raise last_error
        raise RuntimeError("No providers available in FailoverLLMProvider")

    async def stream_generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ):
        last_error = None
        for i, provider in enumerate(self.providers):
            try:
                if i > 0:
                    logger.warning(f"Failover triggered for stream. Using backup provider {i}: {provider.provider_name}")
                async for chunk in provider.stream_generate(messages, temperature=temperature, max_tokens=max_tokens, **kwargs):
                    yield chunk
                return
            except Exception as e:
                last_error = e
                logger.error(f"Provider {i} ({provider.provider_name}) stream failed: {e}")
                if i == len(self.providers) - 1:
                    break
        
        if last_error:
            raise last_error
        raise RuntimeError("No providers available in FailoverLLMProvider")
