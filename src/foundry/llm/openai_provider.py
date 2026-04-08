"""OpenAI LLM provider implementation."""

from typing import Optional, Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from foundry.llm.base import BaseLLMProvider, LLMMessage, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation."""
    
    def __init__(self, model_name: Optional[str] = None, **kwargs: Any) -> None:
        """Initialize OpenAI provider.
        
        Args:
            model_name: Optional model name (defaults to gpt-4-turbo)
            **kwargs: Additional configuration (like API Keys, proxies, etc)
        """
        model = model_name or "gpt-4-turbo"
        super().__init__(model, **kwargs)
        
        # We assume OPENAI_API_KEY is in the environment
        # or passed via kwargs explicitly
        self.client = ChatOpenAI(model=model, **kwargs)
        
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "openai"

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
        """Generate completion from messages using OpenAI."""
        lc_messages = self._convert_messages(messages)
        
        response = await self.client.ainvoke(
            lc_messages, 
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        # Extract token usage from the response metadata
        usage = response.response_metadata.get("token_usage", {})
        tokens_used = usage.get("total_tokens", 0)
        finish_reason = response.response_metadata.get("finish_reason", "stop")
        
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
        """Stream completion from messages using OpenAI."""
        lc_messages = self._convert_messages(messages)
        
        async for chunk in self.client.astream(
            lc_messages, 
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        ):
            if chunk.content:
                yield chunk.content
