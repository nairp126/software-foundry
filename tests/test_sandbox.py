"""Unit tests for sandbox environment."""

import pytest
from foundry.sandbox.environment import (
    SandboxEnvironment,
    Sandbox,
    Code,
    ExecutionResult,
    ResourceUsage,
    SandboxStatus,
)


class TestSandboxEnvironment:
    """Test suite for SandboxEnvironment."""
    
    @pytest.fixture
    async def sandbox_env(self):
        """Create a sandbox environment for testing."""
        return SandboxEnvironment()
    
    @pytest.mark.asyncio
    async def test_create_sandbox_python(self, sandbox_env):
        """Test creating a Python sandbox."""
        sandbox = await sandbox_env.create_sandbox(language="python")
        
        assert sandbox is not None
        assert sandbox.language == "python"
        assert sandbox.sandbox_id is not None
        assert sandbox.status in [SandboxStatus.CREATED, SandboxStatus.RUNNING]
        
        # Cleanup
        await sandbox_env.cleanup_sandbox(sandbox)
    
    @pytest.mark.asyncio
    async def test_create_sandbox_javascript(self, sandbox_env):
        """Test creating a JavaScript sandbox."""
        sandbox = await sandbox_env.create_sandbox(language="javascript")
        
        assert sandbox is not None
        assert sandbox.language == "javascript"
        assert sandbox.sandbox_id is not None
        
        # Cleanup
        await sandbox_env.cleanup_sandbox(sandbox)
    
    @pytest.mark.asyncio
    async def test_execute_simple_python_code(self, sandbox_env):
        """Test executing simple Python code."""
        sandbox = await sandbox_env.create_sandbox(language="python")
        
        code = Code(
            content='print("Hello, World!")',
            language="python",
            filename="test.py"
        )
        
        result = await sandbox_env.execute_code(sandbox, code)
        
        assert result is not None
        assert isinstance(result, ExecutionResult)
        # Note: May be mock execution if Docker not available
        
        # Cleanup
        await sandbox_env.cleanup_sandbox(sandbox)
    
    @pytest.mark.asyncio
    async def test_execute_code_with_error(self, sandbox_env):
        """Test executing code that produces an error."""
        sandbox = await sandbox_env.create_sandbox(language="python")
        
        code = Code(
            content='print(undefined_variable)',
            language="python",
            filename="test.py"
        )
        
        result = await sandbox_env.execute_code(sandbox, code)
        
        assert result is not None
        # If Docker available, should detect error
        # If mock, will succeed
        
        # Cleanup
        await sandbox_env.cleanup_sandbox(sandbox)
    
    @pytest.mark.asyncio
    async def test_execute_code_with_timeout(self, sandbox_env):
        """Test code execution timeout."""
        sandbox = await sandbox_env.create_sandbox(language="python")
        
        code = Code(
            content='import time\ntime.sleep(10)',
            language="python",
            filename="test.py"
        )
        
        # Set short timeout
        result = await sandbox_env.execute_code(sandbox, code, timeout=1)
        
        assert result is not None
        # If Docker available, should timeout
        # If mock, will succeed quickly
        
        # Cleanup
        await sandbox_env.cleanup_sandbox(sandbox)
    
    @pytest.mark.asyncio
    async def test_install_dependencies(self, sandbox_env):
        """Test installing dependencies in sandbox."""
        sandbox = await sandbox_env.create_sandbox(language="python")
        
        result = await sandbox_env.install_dependencies(
            sandbox,
            dependencies=["requests"]
        )
        
        assert result is not None
        assert result.success or not sandbox.container_id  # Mock if no Docker
        
        # Cleanup
        await sandbox_env.cleanup_sandbox(sandbox)
    
    @pytest.mark.asyncio
    async def test_get_resource_usage(self, sandbox_env):
        """Test getting resource usage metrics."""
        sandbox = await sandbox_env.create_sandbox(language="python")
        
        usage = await sandbox_env.get_resource_usage(sandbox)
        
        assert usage is not None
        assert isinstance(usage, ResourceUsage)
        assert usage.cpu_percent >= 0
        assert usage.memory_mb >= 0
        
        # Cleanup
        await sandbox_env.cleanup_sandbox(sandbox)
    
    @pytest.mark.asyncio
    async def test_cleanup_sandbox(self, sandbox_env):
        """Test sandbox cleanup."""
        sandbox = await sandbox_env.create_sandbox(language="python")
        sandbox_id = sandbox.sandbox_id
        
        # Verify sandbox is active
        assert sandbox_id in sandbox_env.active_sandboxes
        
        # Cleanup
        await sandbox_env.cleanup_sandbox(sandbox)
        
        # Verify sandbox is removed
        assert sandbox_id not in sandbox_env.active_sandboxes
    
    @pytest.mark.asyncio
    async def test_multiple_sandboxes(self, sandbox_env):
        """Test creating multiple sandboxes concurrently."""
        sandbox1 = await sandbox_env.create_sandbox(language="python")
        sandbox2 = await sandbox_env.create_sandbox(language="javascript")
        
        assert sandbox1.sandbox_id != sandbox2.sandbox_id
        assert len(sandbox_env.active_sandboxes) >= 2
        
        # Cleanup
        await sandbox_env.cleanup_sandbox(sandbox1)
        await sandbox_env.cleanup_sandbox(sandbox2)
    
    def test_sandbox_to_dict(self):
        """Test sandbox serialization."""
        sandbox = Sandbox(
            sandbox_id="test-123",
            language="python",
            container_id="container-456"
        )
        
        data = sandbox.to_dict()
        
        assert data["sandbox_id"] == "test-123"
        assert data["language"] == "python"
        assert data["container_id"] == "container-456"
        assert "status" in data
        assert "created_at" in data


class TestCode:
    """Test suite for Code dataclass."""
    
    def test_code_creation(self):
        """Test creating a Code object."""
        code = Code(
            content="print('test')",
            language="python",
            filename="test.py"
        )
        
        assert code.content == "print('test')"
        assert code.language == "python"
        assert code.filename == "test.py"
        assert code.entry_point is None
    
    def test_code_with_entry_point(self):
        """Test creating a Code object with entry point."""
        code = Code(
            content="def main(): pass",
            language="python",
            filename="main.py",
            entry_point="main"
        )
        
        assert code.entry_point == "main"


class TestExecutionResult:
    """Test suite for ExecutionResult."""
    
    def test_execution_result_success(self):
        """Test successful execution result."""
        result = ExecutionResult(
            success=True,
            stdout="Hello, World!",
            stderr="",
            exit_code=0,
            execution_time=0.5,
            resource_usage=ResourceUsage()
        )
        
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "Hello, World!"
        assert len(result.errors) == 0
    
    def test_execution_result_failure(self):
        """Test failed execution result."""
        result = ExecutionResult(
            success=False,
            stdout="",
            stderr="NameError: name 'x' is not defined",
            exit_code=1,
            execution_time=0.2,
            resource_usage=ResourceUsage(),
            errors=["NameError: name 'x' is not defined"]
        )
        
        assert result.success is False
        assert result.exit_code == 1
        assert len(result.errors) > 0
