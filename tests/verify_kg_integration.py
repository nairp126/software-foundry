import asyncio
import json
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

# Ensure src is in sys.path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from foundry.agents.product_manager import ProductManagerAgent
from foundry.agents.architect import ArchitectAgent
from foundry.agents.reflexion import ReflexionEngine

class TestKGIntegration(unittest.IsolatedAsyncioTestCase):
    
    async def test_pm_stores_requirements(self):
        # Setup mock KG service
        mock_kg = AsyncMock()
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = AsyncMock(content=json.dumps({
            "project_name": "Test",
            "core_features": ["Feature A"],
            "functional_requirements": ["Req B"],
            "user_stories": ["Story C"],
            "non_functional_requirements": {"security": ["Sec D"]},
            "clarifying_questions": ["Q1"]
        }))
        
        with patch("foundry.services.knowledge_graph.knowledge_graph_service", mock_kg):
            with patch("foundry.llm.factory.LLMProviderFactory.create_provider", return_value=mock_provider):
                agent = ProductManagerAgent()
                await agent.analyze_requirements("Simple Prompt", project_id="test-proj")
                
                # Verify store_requirement was called
                self.assertTrue(mock_kg.store_requirement.called)
                call_count = mock_kg.store_requirement.call_count
                print(f"PM store_requirement calls: {call_count}")
                self.assertGreaterEqual(call_count, 4)

    async def test_architect_stores_pattern(self):
        mock_kg = AsyncMock()
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = AsyncMock(content=json.dumps({
            "high_level_design": "Microservices",
            "tech_stack": {"backend": "FastAPI", "language": "python"},
            "file_structure": ["main.py"]
        }))
        
        with patch("foundry.services.knowledge_graph.knowledge_graph_service", mock_kg):
            with patch("foundry.llm.factory.LLMProviderFactory.create_provider", return_value=mock_provider):
                agent = ArchitectAgent()
                # Mock get_successful_patterns to return empty list
                agent.kg_tools = AsyncMock()
                agent.kg_tools.get_successful_patterns.return_value = []
                
                await agent.design_architecture("Test PRD", project_id="test-proj")
                
                # Verify store_architecture_decision AND store_pattern were called
                self.assertTrue(mock_kg.store_architecture_decision.called)
                self.assertTrue(mock_kg.store_pattern.called)
                print("Architect store_pattern called successfully.")

    async def test_reflexion_stores_error_fix(self):
        mock_kg = AsyncMock()
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = AsyncMock(content=json.dumps({
            "files": {"main.py": "print('fixed')"},
            "explanation": "Simple fix"
        }))
        
        with patch("foundry.services.knowledge_graph.knowledge_graph_service", mock_kg):
            with patch("foundry.llm.factory.LLMProviderFactory.create_provider", return_value=mock_provider):
                agent = ReflexionEngine()
                
                # Mock sandbox results
                agent.execute_code = AsyncMock()
                agent.execute_code.side_effect = [
                    AsyncMock(success=False, stderr="ZeroDivisionError", exit_code=1, execution_time=0.1, stdout=""),
                    AsyncMock(success=True, stderr="", exit_code=0, execution_time=0.1, stdout="fixed")
                ]
                
                # Mock error analyzer
                agent.error_analyzer = MagicMock()
                agent.error_analyzer.analyze_error.return_value = MagicMock(
                    error_type="ArithmeticError", error_message="division by zero", root_cause="missing check"
                )
                
                await agent.execute_and_fix({"main.py": "1/0"}, project_id="test-proj")
                
                # Verify store_error_fix was called
                self.assertTrue(mock_kg.store_error_fix.called)
                print("Reflexion store_error_fix called successfully.")

if __name__ == "__main__":
    unittest.main()
