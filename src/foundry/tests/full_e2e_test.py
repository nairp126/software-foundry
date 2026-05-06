import asyncio
import logging
import uuid
from foundry.orchestrator import AgentOrchestrator, GraphState
from langchain_core.messages import HumanMessage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FullE2ETest")

async def run_e2e_test():
    logger.info("Starting Full E2E System Test...")
    
    orchestrator = AgentOrchestrator()
    project_id = str(uuid.uuid4())
    
    initial_state = {
        "messages": [HumanMessage(content="Create a simple FastAPI app with a single endpoint /health that returns {'status': 'healthy'}. Include a Dockerfile.")],
        "project_id": project_id,
        "current_agent": "product_manager",
        "project_context": {},
        "review_feedback": {},
        "reflexion_count": 0,
        "success_flag": False,
        "language": "python",
        "framework": "fastapi",
        "resume_from": None
    }
    
    logger.info(f"Project ID: {project_id}")
    
    # Run the graph
    # We use stream to see progress
    async for event in orchestrator.graph.astream(initial_state, config={"configurable": {"thread_id": project_id}}):
        for node, output in event.items():
            logger.info(f"--- Node '{node}' completed ---")
            if "messages" in output:
                last_msg = output["messages"][-1].content
                logger.info(f"Output snippet: {last_msg[:100]}...")
            
            # Check for any VRAM metrics logs in the console (from the background tasks)
            # vram_manager should log when it acquires/releases or recalibrates
            
    logger.info("E2E Test Cycle Finished.")

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
