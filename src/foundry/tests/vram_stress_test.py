import asyncio
import time
import logging
import random
from foundry.llm.vram_budget_manager import vram_manager
from foundry.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VRAMStressTest")

class MockProvider(BaseLLMProvider):
    async def generate(self, messages, temperature=0.7, max_tokens=None, **kwargs) -> LLMResponse:
        agent_name = kwargs.pop("agent_name", "unknown")
        context_size = sum(len(m.content) for m in messages) // 4
        
        async with vram_manager.acquire_slot(agent_name=agent_name, provider="mock", context_size=context_size):
            logger.info(f"[START] {agent_name} (Priority: {vram_manager.AGENT_PRIORITIES.get(agent_name, 5)})")
            # Simulate work
            await asyncio.sleep(random.uniform(0.5, 1.5))
            logger.info(f"[END] {agent_name}")
            
        return LLMResponse(
            content="Mocked response",
            model="mock-model",
            tokens_used=100,
            finish_reason="stop",
            metadata={}
        )

    async def stream_generate(self, messages, **kwargs):
        yield "mock"

    @property
    def provider_name(self) -> str:
        return "mock"

async def run_agent(provider, agent_name, messages):
    try:
        await provider.generate(messages, agent_name=agent_name)
    except Exception as e:
        logger.error(f"Agent {agent_name} failed: {e}")

async def stress_test():
    logger.info("Starting VRAM Stress Test...")
    
    # 1. Manually set a low limit for testing
    vram_manager.concurrency_limit = 2
    vram_manager._semaphore.set_limit(2)
    logger.info(f"Concurrency limit set to {vram_manager.concurrency_limit} for test.")

    provider = MockProvider("mock-7b")
    
    # Define a mix of agents
    agents = [
        ("ProductManager", 5),
        ("Architect", 4),
        ("DevOps", 4),
        ("CodeReview", 3),
        ("Reflexion", 2),
        ("Engineer", 1),
    ]
    
    # Randomly shuffle to see if priority re-ordering works
    random.shuffle(agents)
    
    tasks = []
    for agent_name, priority in agents:
        messages = [LLMMessage(role="user", content="Hello " * 100)] # 400 chars ~ 100 tokens
        tasks.append(run_agent(provider, agent_name, messages))
    
    # Start all concurrently
    await asyncio.gather(*tasks)
    
    logger.info("All agents finished.")
    
    # 2. Test Metric Flushing
    project_id = "vram_test_project"
    vram_manager.flush_metrics(project_id)
    
    # 3. Test OOM Prediction (Simulate rapid VRAM drop)
    logger.info("Testing OOM prediction logic...")
    vram_manager._vram_history = [
        (time.time() - 3, 4000),
        (time.time() - 2, 3000),
        (time.time() - 1, 1500),
    ]
    vram_manager._check_oom_risk()
    logger.info(f"Limit after OOM risk check: {vram_manager.concurrency_limit}")

    # 4. Test Priority Escalation (Simulation)
    logger.info("Testing Priority Escalation (Simulation)...")
    vram_manager._semaphore.set_limit(1) # Only one at a time
    
    # Start a slow one
    messages = [LLMMessage(role="user", content="Slow")]
    t1 = asyncio.create_task(provider.generate(messages, agent_name="ProductManager")) # Low priority
    await asyncio.sleep(0.1) # Ensure PM starts first
    
    # Start a fast one that should wait
    t2 = asyncio.create_task(provider.generate(messages, agent_name="Engineer")) # High priority
    
    await asyncio.gather(t1, t2)
    logger.info("Anti-starvation check complete.")

if __name__ == "__main__":
    asyncio.run(stress_test())
