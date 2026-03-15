import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from foundry.agents.architect import ArchitectAgent
from foundry.agents.base import AgentMessage, AgentType, MessageType

async def test_architect_isolation(prd_content):
    print(f"--- ISOLATION TEST: ArchitectAgent ---")
    print(f"Input PRD: {prd_content[:100]}...")
    
    agent = ArchitectAgent()
    message = AgentMessage(
        sender=AgentType.PRODUCT_MANAGER,
        recipient=AgentType.ARCHITECT,
        message_type=MessageType.TASK,
        payload={"prd": prd_content}
    )
    
    response = await agent.process_message(message)
    
    print("\n--- LLM RESPONSE ---")
    if response and "architecture" in response.payload:
        print(response.payload["architecture"])
    else:
        print("FAILED: No Architecture generated or error occurred.")
    print("--- END TEST ---")

if __name__ == "__main__":
    # Default PRD from PM isolation test
    prd = """{
  "Project Name": "Simple Python Calculator",
  "High-Level Description": "A simple Python calculator that can perform addition and subtraction operations.",
  "Core Features (Functional Requirements)": [
    "Addition Functionality",
    "Subtraction Functionality"
  ],
  "User Stories": [
    "As a user, I want to be able to add two numbers together and get the result.",
    "As a user, I want to be able to subtract one number from another and get the result.",
    "As a user, I want the calculator to be simple and easy to use."
  ]
}"""
    if len(sys.argv) > 1:
        prd = sys.argv[1]
    
    asyncio.run(test_architect_isolation(prd))
