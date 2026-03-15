"""
Unit tests for CodeReviewAgent.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch
from foundry.agents.code_review import CodeReviewAgent
from foundry.agents.base import AgentType, AgentMessage, MessageType
from foundry.llm.base import LLMResponse


class TestCodeReviewAgent:
    """Test suites for the CodeReviewAgent."""
    
    @pytest.fixture
    def code_review_agent(self):
        """Create a CodeReviewAgent instance for testing."""
        with patch('foundry.agents.code_review.LLMProviderFactory.create_provider'):
            agent = CodeReviewAgent(model_name="qwen2.5-coder:7b")
            agent.llm = AsyncMock()
            return agent

    @pytest.mark.asyncio
    async def test_process_message_task(self, code_review_agent):
        """Test processing a TASK message."""
        # Mock LLM response
        review_content = {
            "status": "APPROVED",
            "feedback": "Code looks good.",
            "issues": []
        }
        code_review_agent.llm.generate.return_value = LLMResponse(
            content=json.dumps(review_content),
            model="qwen2.5-coder:7b",
            tokens_used=100,
            finish_reason="stop",
            metadata={}
        )

        message = AgentMessage(
            sender=AgentType.ENGINEER,
            recipient=AgentType.CODE_REVIEW,
            message_type=MessageType.TASK,
            payload={"code_repo": {"main.py": "print('hello')"}}
        )

        response = await code_review_agent.process_message(message)

        assert response.sender == AgentType.CODE_REVIEW
        assert response.recipient == AgentType.DEVOPS
        assert response.message_type == MessageType.TASK
        # The payload now contains the review data directly (not nested under "review")
        assert response.payload.get("status") == "APPROVED"

    @pytest.mark.asyncio
    async def test_analyze_code_approved(self, code_review_agent):
        """Test code analysis resulting in APPROVED status."""
        review_content = {
            "status": "APPROVED",
            "feedback": "Clean and efficient code.",
            "issues": []
        }
        code_review_agent.llm.generate.return_value = LLMResponse(
            content=json.dumps(review_content),
            model="qwen2.5-coder:7b",
            tokens_used=120,
            finish_reason="stop",
            metadata={}
        )

        code_files = {"app.py": "def add(a, b): return a + b"}
        response = await code_review_agent.analyze_code(code_files)

        assert response.message_type == MessageType.TASK
        # The payload now contains the review data directly
        assert response.payload.get("status") == "APPROVED"

    @pytest.mark.asyncio
    async def test_analyze_code_rejected(self, code_review_agent):
        """Test code analysis resulting in REJECTED status due to issues."""
        review_content = {
            "status": "REJECTED",
            "feedback": "Hardcoded secret found.",
            "issues": [
                {
                    "severity": "CRITICAL",
                    "file": "config.py",
                    "line": 5,
                    "description": "Hardcoded API key",
                    "suggestion": "Use environment variables"
                }
            ]
        }
        code_review_agent.llm.generate.return_value = LLMResponse(
            content=json.dumps(review_content),
            model="qwen2.5-coder:7b",
            tokens_used=180,
            finish_reason="stop",
            metadata={}
        )

        code_files = {"config.py": "API_KEY = 'sk-123456789'"}
        response = await code_review_agent.analyze_code(code_files)

        # The payload now contains the review data directly
        assert response.payload.get("status") == "REJECTED"
        assert len(response.payload.get("issues", [])) == 1
        assert response.payload["issues"][0]["severity"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_analyze_empty_code(self, code_review_agent):
        """Test handling of empty code repository."""
        response = await code_review_agent.analyze_code({})

        assert response.recipient == AgentType.REFLEXION
        # The payload now contains the review data directly
        assert response.payload.get("status") == "REJECTED"
        assert "No code was provided" in response.payload.get("feedback", "")
