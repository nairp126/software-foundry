import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from foundry.agents.engineer import EngineerAgent
from foundry.agents.base import AgentMessage, AgentType, MessageType

async def test_engineer_isolation(architecture_content, prd_content):
    print(f"--- ISOLATION TEST: EngineerAgent ---")
    print(f"Input Arch: {architecture_content[:100]}...")
    
    agent = EngineerAgent()
    message = AgentMessage(
        sender=AgentType.ARCHITECT,
        recipient=AgentType.ENGINEER,
        message_type=MessageType.TASK,
        payload={
            "architecture": architecture_content,
            "prd": prd_content,
            "project_id": "isolation_test"
        }
    )
    
    response = await agent.process_message(message)
    
    print("\n--- LLM RESPONSE (FILES) ---")
    if response and "code_repo" in response.payload:
        files = response.payload["code_repo"]
        if not files:
            print("EMPTY REPO: No files generated.")
        for filename, content in files.items():
            print(f"\nFILE: {filename}")
            print("-" * 20)
            print(content)
            print("-" * 20)
    else:
        print(f"FAILED: No code_repo in payload. Keys: {list(response.payload.keys()) if response else 'None'}")
    print("--- END TEST ---")

if __name__ == "__main__":
    prd = """{"Project Name": "Simple Python Calculator", ...}"""
    arch = """{
  "Project Name": "Simple Python Calculator",
  "High-Level Architecture": {
    "Technology Stack": {"Backend": "FastAPI"}
  },
  "File Structure": {
    "src": {
      "main.py": "Main entry point",
      "calculator.py": "Calculator logic"
    }
  }
}"""
    asyncio.run(test_engineer_isolation(arch, prd))
