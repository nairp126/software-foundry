import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from foundry.agents.product_manager import ProductManagerAgent
from foundry.agents.base import AgentMessage, AgentType, MessageType

async def test_pm_isolation(prompt):
    print(f"--- ISOLATION TEST: ProductManagerAgent ---")
    print(f"Input Prompt: {prompt}")
    
    agent = ProductManagerAgent()
    message = AgentMessage(
        sender=AgentType.PRODUCT_MANAGER,
        recipient=AgentType.PRODUCT_MANAGER,
        message_type=MessageType.TASK,
        payload={"prompt": prompt}
    )
    
    response = await agent.process_message(message)
    
    print("\n--- LLM RESPONSE ---")
    if response and "prd" in response.payload:
        print(response.payload["prd"])
    else:
        print("FAILED: No PRD generated or error occurred.")
    print("--- END TEST ---")

if __name__ == "__main__":
    prompt = "Create a simple Python calculator with addition and subtraction functions."
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
    
    asyncio.run(test_pm_isolation(prompt))
