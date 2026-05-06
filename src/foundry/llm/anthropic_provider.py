"""Anthropic LLM provider implementation."""

from typing import Optional, Dict, Any, List
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from foundry.llm.base import BaseLLMProvider, LLMMessage, LLMResponse


class AnthropicProvider(BaseLLMProvider):
    """Anthropic provider implementation."""
    
    def __init__(self, model_name: Optional[str] = None, **kwargs: Any) -> None:
        """Initialize Anthropic provider.
        
        Args:
            model_name: Optional model name (defaults to claude-3-opus-20240229)
            **kwargs: Additional configuration (like API Keys, proxies, etc)
        """
        model = model_name or "claude-3-opus-20240229"
        super().__init__(model, **kwargs)
        
        # We assume ANTHROPIC_API_KEY is in the environment
        # or passed via kwargs explicitly
        self.client = ChatAnthropic(model=model, **kwargs)
        
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "anthropic"

    def _convert_messages(self, messages: List[LLMMessage]) -> List[BaseMessage]:
        """Convert internal LLM messages to LangChain format."""
        converted = []
        for msg in messages:
            if msg.role == "system":
                converted.append(SystemMessage(content=msg.content))
            elif msg.role in ["user", "human"]:
                converted.append(HumanMessage(content=msg.content))
            elif msg.role in ["assistant", "ai"]:
                converted.append(AIMessage(content=msg.content))
        return converted
        
    async def generate(
        self, 
        messages: List[LLMMessage], 
        temperature: float = 0.7, 
        max_tokens: Optional[int] = None, 
        **kwargs: Any
    ) -> LLMResponse:
        """Generate completion from messages using Anthropic."""
        lc_messages = self._convert_messages(messages)
        kwargs.pop("agent_name", None)
        response = await self.client.ainvoke(
            lc_messages, 
            temperature=temperature,
            max_tokens=max_tokens or 4096,  # Anthropic requires max_tokens or defaults low
            **kwargs
        )
        
        # Extract token usage from the response metadata
        usage = response.response_metadata.get("usage", {})
        tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        finish_reason = response.response_metadata.get("stop_reason", "stop")
        
        return LLMResponse(
            content=response.content,
            model=self.model_name,
            tokens_used=tokens_used,
            finish_reason=finish_reason,
            metadata=response.response_metadata
        )

    async def stream_generate(
        self, 
        messages: List[LLMMessage], 
        temperature: float = 0.7, 
        max_tokens: Optional[int] = None, 
        **kwargs: Any
    ):
        """Stream completion from messages using Anthropic."""
        lc_messages = self._convert_messages(messages)
        kwargs.pop("agent_name", None)
        async for chunk in self.client.astream(
            lc_messages, 
            temperature=temperature,
            max_tokens=max_tokens or 4096,
            **kwargs
        ):
            if chunk.content:
                yield chunk.content
