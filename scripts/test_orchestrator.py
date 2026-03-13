import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from foundry.orchestrator import AgentOrchestrator

async def main():
    print("Initializing Orchestrator...")
    try:
        orchestrator = AgentOrchestrator()
        print("Orchestrator initialized.")
        
        print("Running project workflow...")
        await orchestrator.run_project("Build a simple todo app with React frontend and FastAPI backend.")
        print("Project workflow completed successfully.")
    except Exception as e:
        print(f"Error running orchestrator: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
