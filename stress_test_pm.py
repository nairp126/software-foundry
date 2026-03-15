import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from foundry.agents.product_manager import ProductManagerAgent
from foundry.agents.base import AgentMessage, AgentType, MessageType

async def stress_test_pm(prompt, iterations=5):
    print(f"--- STRESS TEST: ProductManagerAgent ({iterations} runs) ---")
    agent = ProductManagerAgent()
    
    drifts = 0
    for i in range(iterations):
        message = AgentMessage(
            sender=AgentType.PRODUCT_MANAGER,
            recipient=AgentType.PRODUCT_MANAGER,
            message_type=MessageType.TASK,
            payload={"prompt": prompt}
        )
        
        response = await agent.process_message(message)
        prd = response.payload.get("prd", "").lower()
        
        # Check for calculator keywords
        if "calculator" in prd or "addition" in prd:
            print(f"Run {i+1}: SUCCESS")
        else:
            print(f"Run {i+1}: DRIFTED! (First 50 chars: {prd[:50]})")
            drifts += 1
            
    print(f"--- SUMMARY: {drifts}/{iterations} drifted ---")

if __name__ == "__main__":
    prompt = "Create a simple Python calculator with addition and subtraction functions."
    asyncio.run(stress_test_pm(prompt, 5))
