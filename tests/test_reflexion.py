"""Unit tests for Reflexion Engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from foundry.agents.reflexion import ReflexionEngine
from foundry.agents.base import AgentType, MessageType, AgentMessage
from foundry.sandbox.environment import (
    Code,
    ExecutionResult,
    ResourceUsage,
)
from foundry.sandbox.error_analysis import (
    ErrorAnalysis,
    ErrorType,
    ErrorSeverity,
    CodeFix,
)


class TestReflexionEngine:
    """Test suite for ReflexionEngine."""
    
    @pytest.fixture
    def reflexion_engine(self):
        """Create a reflexion engine for testing."""
        return ReflexionEngine(model_name="qwen2.5-coder:7b")
    
    def test_initialization(self, reflexion_engine):
        """Test reflexion engine initialization."""
        assert reflexion_engine.agent_type == AgentType.REFLEXION
        assert reflexion_engine.MAX_RETRY_ATTEMPTS == 5
        assert reflexion_engine.sandbox_env is not None
        assert reflexion_engine.error_analyzer is not None
        assert reflexion_engine.fix_generator is not None
    
    @pytest.mark.asyncio
    async def test_execute_code_success(self, reflexion_engine):
        """Test successful code execution."""
        code_repo = {"test.py": 'print("Hello, World!")'}
        
        result = await reflexion_engine.execute_code(
            code_repo=code_repo,
            environment=reflexion_engine.sandbox_env,
            language="python",
            entry_point="test.py"
        )
        
        assert result is not None
        assert isinstance(result, ExecutionResult)
    
    @pytest.mark.asyncio
    async def test_analyze_errors(self, reflexion_engine):
        """Test error analysis."""
        result = ExecutionResult(
            success=False,
            stdout="",
            stderr="NameError: name 'x' is not defined",
            exit_code=1,
            execution_time=0.1,
            resource_usage=ResourceUsage(),
            errors=["NameError: name 'x' is not defined"]
        )
        
        analysis = await reflexion_engine.analyze_errors(result)
        
        assert analysis is not None
        assert isinstance(analysis, ErrorAnalysis)
        assert analysis.error_type in ErrorType
    
    @pytest.mark.asyncio
    async def test_generate_fixes(self, reflexion_engine):
        """Test fix generation."""
        analysis = ErrorAnalysis(
            error_type=ErrorType.NAME_ERROR,
            severity=ErrorSeverity.HIGH,
            error_message="NameError: name 'x' is not defined",
            stack_trace=[],
            root_cause="Variable not defined",
            affected_lines=[1],
            suggested_fixes=["Define x before use"]
        )
        
        code_content = "print(x)"
        
        # Mock LLM response for fix generation
        with patch.object(reflexion_engine.llm, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_response = MagicMock()
            mock_response.content = "x = None\nprint(x)"
            mock_generate.return_value = mock_response
            
            fixes = await reflexion_engine.generate_fixes(analysis, code_content)
            
            assert len(fixes) > 0
            assert isinstance(fixes[0], CodeFix)
    
    @pytest.mark.asyncio
    async def test_apply_fixes_replace(self, reflexion_engine):
        """Test applying replace fixes."""
        code = Code(
            content="print(x)",
            language="python",
            filename="test.py"
        )
        
        fixes = [
            CodeFix(
                fix_type="replace",
                target_file="test.py",
                line_number=None,
                original_code="print(x)",
                fixed_code="x = None\nprint(x)",
                explanation="Initialize variable"
            )
        ]
        
        updated_code = await reflexion_engine.apply_fixes(code, fixes)
        
        assert updated_code.content == "x = None\nprint(x)"
    
    @pytest.mark.asyncio
    async def test_apply_fixes_insert(self, reflexion_engine):
        """Test applying insert fixes."""
        code = Code(
            content="print(x)",
            language="python",
            filename="test.py"
        )
        
        fixes = [
            CodeFix(
                fix_type="insert",
                target_file="test.py",
                line_number=0,
                original_code=None,
                fixed_code="x = None",
                explanation="Initialize variable"
            )
        ]
        
        updated_code = await reflexion_engine.apply_fixes(code, fixes)
        
        assert "x = None" in updated_code.content
    
    def test_should_escalate_max_retries(self, reflexion_engine):
        """Test escalation when max retries exceeded."""
        result = ExecutionResult(
            success=False,
            stdout="",
            stderr="Error",
            exit_code=1,
            execution_time=0.1,
            resource_usage=ResourceUsage(),
            errors=["Error"]
        )
        
        should_escalate = reflexion_engine.should_escalate(
            attempt_count=5,
            error=result
        )
        
        assert should_escalate is True
    
    def test_should_escalate_memory_error(self, reflexion_engine):
        """Test escalation for memory errors."""
        result = ExecutionResult(
            success=False,
            stdout="",
            stderr="MemoryError: out of memory",
            exit_code=1,
            execution_time=0.1,
            resource_usage=ResourceUsage(),
            errors=["MemoryError"]
        )
        
        should_escalate = reflexion_engine.should_escalate(
            attempt_count=1,
            error=result
        )
        
        assert should_escalate is True
    
    def test_should_not_escalate_early(self, reflexion_engine):
        """Test no escalation on early attempts."""
        result = ExecutionResult(
            success=False,
            stdout="",
            stderr="NameError: name 'x' is not defined",
            exit_code=1,
            execution_time=0.1,
            resource_usage=ResourceUsage(),
            errors=["NameError"]
        )
        
        should_escalate = reflexion_engine.should_escalate(
            attempt_count=2,
            error=result
        )
        
        assert should_escalate is False
    
    @pytest.mark.asyncio
    async def test_execute_and_fix_success(self, reflexion_engine):
        """Test execute_and_fix with successful execution."""
        code_repo = {"test.py": 'print("Hello, World!")'}
        
        # Mock successful execution
        with patch.object(reflexion_engine, 'execute_code', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = ExecutionResult(
                success=True,
                stdout="Hello, World!",
                stderr="",
                exit_code=0,
                execution_time=0.1,
                resource_usage=ResourceUsage(),
                errors=[]
            )
            
            message = await reflexion_engine.execute_and_fix(
                code_repo=code_repo,
                language="python",
                entry_point="test.py"
            )
            
            assert message.message_type == MessageType.RESPONSE
            assert message.payload["status"] == "success"
            assert message.payload["result"]["attempts"] == 1
    
    @pytest.mark.asyncio
    async def test_execute_and_fix_with_retry(self, reflexion_engine):
        """Test execute_and_fix with retry logic."""
        code_repo = {"test.py": "print(x)"}
        
        # Mock first execution fails, second succeeds
        execution_results = [
            ExecutionResult(
                success=False,
                stdout="",
                stderr="NameError: name 'x' is not defined",
                exit_code=1,
                execution_time=0.1,
                resource_usage=ResourceUsage(),
                errors=["NameError"]
            ),
            ExecutionResult(
                success=True,
                stdout="None",
                stderr="",
                exit_code=0,
                execution_time=0.1,
                resource_usage=ResourceUsage(),
                errors=[]
            )
        ]
        
        with patch.object(reflexion_engine, 'execute_code', new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = execution_results
            
            with patch.object(reflexion_engine.llm, 'generate', new_callable=AsyncMock) as mock_gen:
                mock_response = MagicMock()
                mock_response.content = "x = None\nprint(x)"
                mock_gen.return_value = mock_response
                
                message = await reflexion_engine.execute_and_fix(
                    code_repo=code_repo,
                    language="python",
                    entry_point="test.py"
                )
                
                assert message.message_type in (MessageType.RESPONSE, MessageType.TASK)
    
    @pytest.mark.asyncio
    async def test_execute_and_fix_escalation(self, reflexion_engine):
        """Test execute_and_fix escalation after max retries."""
        code_repo = {"test.py": "print(x)"}
        
        # Mock all executions fail
        with patch.object(reflexion_engine, 'execute_code', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = ExecutionResult(
                success=False,
                stdout="",
                stderr="MemoryError: out of memory",
                exit_code=1,
                execution_time=0.1,
                resource_usage=ResourceUsage(),
                errors=["MemoryError"]
            )
            
            message = await reflexion_engine.execute_and_fix(
                code_repo=code_repo,
                language="python",
                entry_point="test.py"
            )
            
            assert message.message_type == MessageType.ERROR
            assert "escalated" in message.payload["status"] or "failed" in message.payload["status"]
    
    @pytest.mark.asyncio
    async def test_process_message_execute_and_fix(self, reflexion_engine):
        """Test processing execute_and_fix message."""
        message = AgentMessage(
            sender=AgentType.ENGINEER,
            recipient=AgentType.REFLEXION,
            message_type=MessageType.TASK,
            payload={
                "task_type": "execute_and_fix",
                "code": 'print("test")',
                "language": "python",
                "filename": "test.py",
                "dependencies": []
            }
        )
        
        with patch.object(reflexion_engine, 'execute_and_fix', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = AgentMessage(
                sender=AgentType.REFLEXION,
                recipient=AgentType.ENGINEER,
                message_type=MessageType.RESPONSE,
                payload={"status": "success"}
            )
            
            response = await reflexion_engine.process_message(message)
            
            assert response is not None
            assert response.message_type == MessageType.RESPONSE
    
    @pytest.mark.asyncio
    async def test_reflect_on_feedback_legacy(self, reflexion_engine):
        """Test legacy reflect_on_feedback method."""
        code_review = {
            "issues": ["Missing error handling"],
            "severity": "high"
        }
        original_code = {"main.py": "def func(): pass"}
        
        with patch.object(reflexion_engine.llm, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_response = MagicMock()
            mock_response.content = "Add try-catch blocks"
            mock_generate.return_value = mock_response
            
            message = await reflexion_engine.reflect_on_feedback(
                code_review=code_review,
                original_code=original_code
            )
            
            assert message is not None
            assert message.message_type == MessageType.TASK
            assert "fix_plan" in message.payload
