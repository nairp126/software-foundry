import asyncio
import time
import logging
from unittest.mock import AsyncMock, patch
from foundry.llm.vram_budget_manager import vram_manager
from foundry.llm.ollama_provider import OllamaProvider
from foundry.llm.vllm_provider import VLLMProvider
from foundry.llm.base import LLMMessage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CrossProviderVRAMTest")

async def test_cross_provider_vram():
    logger.info("Starting Cross-Provider VRAM Singleton Test...")
    
    # 1. Force a strict concurrency limit on the singleton
    vram_manager.concurrency_limit = 2
    vram_manager._semaphore.set_limit(2)
    logger.info(f"Set VRAM Manager concurrency limit to: {vram_manager.concurrency_limit}")

    # Track maximum observed active slots to ensure limit is never breached
    max_observed_active = 0
    lock = asyncio.Lock()

    async def tracked_sleep(duration):
        nonlocal max_observed_active
        async with lock:
            current_active = vram_manager._semaphore.active_count
            if current_active > max_observed_active:
                max_observed_active = current_active
            logger.info(f"Active slots: {current_active}/{vram_manager.concurrency_limit}")
        await asyncio.sleep(duration)

    # 2. Mock HTTP clients to prevent actual network calls but keep the semaphore logic
    ollama_provider = OllamaProvider(model_name="mock-ollama")
    vllm_provider = VLLMProvider(model_name="mock-vllm")
    
    class MockResponse:
        def __init__(self, json_data):
            self.status_code = 200
            self._json_data = json_data
        
        def json(self):
            return self._json_data
            
        def raise_for_status(self):
            pass

    mock_ollama_response = MockResponse({
        "message": {"content": "Ollama response"},
        "eval_count": 10,
        "prompt_eval_count": 5
    })
    
    async def mock_ollama_post(*args, **kwargs):
        await tracked_sleep(0.5)
        return mock_ollama_response

    ollama_provider.client.post = mock_ollama_post
    ollama_provider._check_connection = AsyncMock() # Bypass proactive connection check

    mock_vllm_response = MockResponse({
        "choices": [{"message": {"content": "vLLM response"}}],
        "usage": {"total_tokens": 15}
    })
    
    async def mock_vllm_post(*args, **kwargs):
        await tracked_sleep(0.5)
        return mock_vllm_response

    vllm_provider.client.post = mock_vllm_post

    # 3. Fire concurrent requests from both providers
    messages = [LLMMessage(role="user", content="Test cross-provider budget limit")]
    
    logger.info("Firing 5 concurrent requests (3 Ollama, 2 vLLM)...")
    tasks = [
        asyncio.create_task(ollama_provider.generate(messages, agent_name="Engineer")),
        asyncio.create_task(vllm_provider.generate(messages, agent_name="Architect")),
        asyncio.create_task(ollama_provider.generate(messages, agent_name="ProductManager")),
        asyncio.create_task(vllm_provider.generate(messages, agent_name="CodeReview")),
        asyncio.create_task(ollama_provider.generate(messages, agent_name="DevOps"))
    ]

    await asyncio.gather(*tasks)
    
    # 4. Verify limits were respected
    logger.info(f"Maximum observed concurrent slots during execution: {max_observed_active}")
    assert max_observed_active <= 2, f"Concurrency limit breached! Observed {max_observed_active} active slots."
    
    logger.info("SUCCESS: Cross-provider VRAM singleton test passed.")
    logger.info("OllamaProvider and VLLMProvider jointly respect the same VRAM Budget limits.")

if __name__ == "__main__":
    asyncio.run(test_cross_provider_vram())
