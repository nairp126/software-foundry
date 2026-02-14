"""Test script for LLM provider integration."""

import asyncio
from foundry.llm.factory import LLMProviderFactory
from foundry.llm.base import LLMMessage


async def test_vllm_provider():
    """Test vLLM provider with Qwen model."""
    print("Testing vLLM Provider with Qwen Model")
    print("=" * 50)
    
    try:
        # Create provider
        provider = LLMProviderFactory.get_default_provider()
        print(f"✓ Created provider: {provider.provider_name}")
        print(f"✓ Model: {provider.model_name}")
        
        # Test basic generation
        messages = [
            LLMMessage(
                role="system",
                content="You are a helpful coding assistant specialized in Python."
            ),
            LLMMessage(
                role="user",
                content="Write a Python function to calculate the nth Fibonacci number using dynamic programming."
            )
        ]
        
        print("\n📝 Generating code...")
        response = await provider.generate(messages, temperature=0.3, max_tokens=500)
        
        print(f"\n✓ Generation complete!")
        print(f"  Model: {response.model}")
        print(f"  Tokens used: {response.tokens_used}")
        print(f"  Finish reason: {response.finish_reason}")
        print(f"\n📄 Generated code:\n")
        print(response.content)
        
        # Test streaming
        print("\n" + "=" * 50)
        print("Testing streaming generation...")
        print("=" * 50)
        
        stream_messages = [
            LLMMessage(
                role="system",
                content="You are a helpful coding assistant."
            ),
            LLMMessage(
                role="user",
                content="Explain what a binary search tree is in 2-3 sentences."
            )
        ]
        
        print("\n📝 Streaming response:")
        async for chunk in provider.stream_generate(stream_messages, temperature=0.5):
            print(chunk, end="", flush=True)
        
        print("\n\n✓ All tests passed!")
        
        # Cleanup
        await provider.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure vLLM server is running: python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-Coder-32B-Instruct --port 8001")
        print("2. Check VLLM_BASE_URL in .env file")
        print("3. Verify GPU is available and has sufficient VRAM")
        raise


if __name__ == "__main__":
    asyncio.run(test_vllm_provider())
