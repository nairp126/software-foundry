# Reflexion Engine Documentation

## Overview

The Reflexion Engine is a self-healing system that automatically detects and corrects errors in generated code through iterative execution and analysis. It implements the **Execute → Analyze → Fix → Retry → Escalate** workflow to ensure code quality and functionality.

## Architecture

### Core Components

1. **SandboxEnvironment**: Docker-based isolated execution environment
2. **ErrorAnalyzer**: Analyzes execution errors and determines root causes
3. **FixGenerator**: Generates code fixes based on error analysis
4. **ReflexionEngine**: Orchestrates the entire workflow

### Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    Reflexion Engine Workflow                 │
└─────────────────────────────────────────────────────────────┘

    ┌──────────┐
    │  Start   │
    └────┬─────┘
         │
         ▼
    ┌──────────────┐
    │   Execute    │◄──────────────┐
    │   in Sandbox │               │
    └────┬─────────┘               │
         │                         │
         ▼                         │
    ┌──────────────┐               │
    │   Success?   │               │
    └────┬─────────┘               │
         │                         │
    ┌────┴────┐                    │
    │ Yes│ No │                    │
    │    │    │                    │
    ▼    │    ▼                    │
  ┌────┐│  ┌──────────────┐       │
  │Done││  │   Analyze    │       │
  └────┘│  │   Errors     │       │
        │  └────┬─────────┘       │
        │       │                 │
        │       ▼                 │
        │  ┌──────────────┐       │
        │  │  Max Retries │       │
        │  │  Exceeded?   │       │
        │  └────┬─────────┘       │
        │       │                 │
        │  ┌────┴────┐            │
        │  │ Yes│ No │            │
        │  │    │    │            │
        │  ▼    │    ▼            │
        │┌────┐ │  ┌──────────┐   │
        ││Esca││  │ Generate │   │
        ││late││  │  Fixes   │   │
        │└────┘ │  └────┬─────┘   │
        │       │       │         │
        │       │       ▼         │
        │       │  ┌──────────┐   │
        │       │  │  Apply   │   │
        │       │  │  Fixes   │   │
        │       │  └────┬─────┘   │
        │       │       │         │
        │       │       └─────────┘
        │       │
        └───────┘
```

## Security Features

### Sandbox Isolation

The Reflexion Engine uses Docker containers with strict security constraints:

- **Complete Host Isolation**: Containers cannot access host filesystem or processes
- **Resource Limits**:
  - 2 vCPUs maximum
  - 4GB RAM maximum
  - 2GB disk space maximum
  - 5-minute execution timeout
- **Read-Only Root Filesystem**: Prevents malicious code from modifying system files
- **Dropped Capabilities**: All Linux capabilities dropped for maximum security
- **Network Restrictions**: Only outbound HTTPS/HTTP allowed, internal ranges blocked
- **No Privilege Escalation**: Security option prevents gaining additional privileges

### Example Sandbox Configuration

```python
docker run \
  --rm \
  --cpus=2 \
  --memory=4096m \
  --network=bridge \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  --tmpfs=/tmp:rw,noexec,nosuid,size=2g \
  --tmpfs=/sandbox:rw,exec,size=2048m \
  python:3.11-slim
```

## Error Analysis

### Supported Error Types

The ErrorAnalyzer can detect and classify the following error types:

1. **SyntaxError**: Code syntax issues
2. **NameError**: Undefined variables or functions
3. **ImportError/ModuleNotFoundError**: Missing modules
4. **TypeError**: Type mismatches
5. **AttributeError**: Non-existent attributes
6. **IndexError**: Array/list index out of bounds
7. **KeyError**: Dictionary key not found
8. **ValueError**: Invalid values
9. **TimeoutError**: Execution timeout
10. **MemoryError**: Out of memory

### Error Severity Levels

- **CRITICAL**: Memory errors, system failures (immediate escalation)
- **HIGH**: Syntax errors, import errors, name errors
- **MEDIUM**: Type errors, attribute errors, index errors
- **LOW**: Style violations, minor issues

### Root Cause Analysis

The ErrorAnalyzer performs root cause analysis by:

1. Extracting stack traces from stderr
2. Identifying error patterns using regex
3. Extracting affected line numbers
4. Analyzing error context
5. Generating actionable fix suggestions

## Fix Generation

### Rule-Based Fixes

For common errors, the FixGenerator applies rule-based fixes:

- **ImportError**: Add missing import statements
- **NameError**: Initialize undefined variables
- **Simple syntax issues**: Apply known patterns

### LLM-Based Fixes

For complex errors, the Reflexion Engine uses the LLM (Qwen2.5-Coder) to:

1. Analyze the error context
2. Understand the intended functionality
3. Generate corrected code
4. Preserve original logic while fixing issues

## Usage

### Basic Usage

```python
from foundry.agents.reflexion import ReflexionEngine

# Create engine
engine = ReflexionEngine(model_name="qwen2.5-coder:7b")

# Execute and fix code
message = await engine.execute_and_fix(
    code_content='''
    def calculate(x, y):
        return x + y
    
    result = calculate(5, 10)
    print(result)
    ''',
    language="python",
    filename="calculator.py"
)

# Check result
if message.payload['status'] == 'success':
    print("Code executed successfully!")
    print(f"Attempts: {message.payload['result']['attempts']}")
    print(f"Output: {message.payload['result']['stdout']}")
elif message.payload['status'] == 'escalated':
    print("Error escalated to human intervention")
    print(f"Reason: {message.payload['reason']}")
```

### With Dependencies

```python
message = await engine.execute_and_fix(
    code_content='''
    import requests
    
    response = requests.get('https://api.example.com')
    print(response.status_code)
    ''',
    language="python",
    filename="api_test.py",
    dependencies=["requests"]
)
```

### Agent Message Protocol

```python
from foundry.agents.base import AgentMessage, AgentType, MessageType

# Send task to Reflexion Engine
task_message = AgentMessage(
    sender=AgentType.ENGINEER,
    recipient=AgentType.REFLEXION,
    message_type=MessageType.TASK,
    payload={
        "task_type": "execute_and_fix",
        "code": "print('Hello, World!')",
        "language": "python",
        "filename": "hello.py",
        "dependencies": []
    }
)

response = await engine.process_message(task_message)
```

## Configuration

### Environment Variables

```bash
# Ollama configuration (default LLM provider)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=qwen2.5-coder:7b


# Default provider
DEFAULT_LLM_PROVIDER=ollama
```

### Retry Configuration

The maximum number of retry attempts is configurable:

```python
# Default: 5 attempts (as per Requirement 5.5)
ReflexionEngine.MAX_RETRY_ATTEMPTS = 5

# Custom configuration
engine = ReflexionEngine()
engine.MAX_RETRY_ATTEMPTS = 3  # Reduce for faster feedback
```

## Escalation

### When Escalation Occurs

The Reflexion Engine escalates to human intervention when:

1. **Max Retries Exceeded**: After 5 failed attempts
2. **Critical Errors**: Memory errors, system failures
3. **No Fixes Generated**: Unable to generate fixes for the error
4. **Persistent Failures**: Same error persists after multiple fix attempts

### Escalation Response

```python
{
    "status": "escalated",
    "reason": "Failed after 5 attempts",
    "last_error": {
        "stdout": "",
        "stderr": "NameError: name 'x' is not defined",
        "exit_code": 1
    },
    "execution_history": [
        {"attempt": 1, "success": False, "exit_code": 1},
        {"attempt": 2, "success": False, "exit_code": 1},
        # ...
    ]
}
```

## Performance

### Execution Times

- **Simple code**: 0.1-0.5 seconds
- **With dependencies**: 2-10 seconds (first time, cached after)
- **Complex fixes**: 1-5 seconds per retry
- **Total workflow**: Typically 5-30 seconds depending on complexity

### Resource Usage

- **Memory**: ~100-500 MB per sandbox
- **CPU**: Minimal (limited to 2 vCPUs per sandbox)
- **Disk**: ~50-200 MB per sandbox (temporary)

## Testing

### Unit Tests

```bash
# Test sandbox environment
pytest tests/test_sandbox.py -v

# Test error analysis
pytest tests/test_error_analysis.py -v

# Test Reflexion Engine
pytest tests/test_reflexion.py -v
```

### Integration Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=foundry.sandbox --cov=foundry.agents.reflexion
```

### Demo Script

```bash
# Run comprehensive demo
python examples/reflexion_demo.py
```

## Limitations

### Current Limitations

1. **Language Support**: Currently optimized for Python, JavaScript, TypeScript
2. **Complex Errors**: Some complex logic errors may require human intervention
3. **External Dependencies**: Cannot install system-level dependencies
4. **Network Access**: Limited to outbound HTTP/HTTPS only
5. **Execution Time**: 5-minute maximum per execution

### Future Enhancements

1. **Knowledge Graph Integration**: Store error patterns and fixes for learning
2. **Multi-Language Support**: Enhanced support for Java, Go, Rust
3. **Parallel Execution**: Run multiple sandboxes concurrently
4. **Advanced Analysis**: Use static analysis tools before execution
5. **Custom Fix Strategies**: User-defined fix patterns

## Best Practices

### Code Organization

1. **Keep code modular**: Smaller functions are easier to fix
2. **Add type hints**: Helps with type error detection
3. **Include docstrings**: Provides context for fix generation
4. **Handle errors explicitly**: Add try-catch blocks for known issues

### Error Handling

1. **Start simple**: Test basic functionality first
2. **Incremental complexity**: Add features gradually
3. **Monitor attempts**: Check execution history for patterns
4. **Review escalations**: Learn from errors that require human intervention

### Performance Optimization

1. **Cache dependencies**: Install once, reuse across executions
2. **Use timeouts**: Set appropriate timeouts for different code types
3. **Limit retries**: Reduce MAX_RETRY_ATTEMPTS for faster feedback
4. **Clean up sandboxes**: Always cleanup to free resources

## Troubleshooting

### Docker Not Available

If Docker is not available, the Reflexion Engine falls back to mock execution:

```python
# Check Docker availability
if not await sandbox_env._check_docker_available():
    print("Docker not available, using mock execution")
```

### Timeout Issues

If code consistently times out:

1. Increase timeout: `execute_code(sandbox, code, timeout=600)`
2. Optimize code: Review for infinite loops or inefficient algorithms
3. Check resource limits: Ensure adequate CPU/memory

### Fix Generation Failures

If fixes are not generated:

1. Check LLM availability: Ensure Ollama is running
2. Review error messages: Some errors may be too complex
3. Add context: Provide more detailed error information
4. Manual intervention: Review and fix manually if needed

## API Reference

### ReflexionEngine

```python
class ReflexionEngine(Agent):
    """Self-healing system for automatic error detection and correction."""
    
    MAX_RETRY_ATTEMPTS = 5
    
    async def execute_code(
        self, code: Code, environment: SandboxEnvironment
    ) -> ExecutionResult
    
    async def analyze_errors(
        self, result: ExecutionResult
    ) -> ErrorAnalysis
    
    async def generate_fixes(
        self, analysis: ErrorAnalysis, code_content: str
    ) -> List[CodeFix]
    
    async def apply_fixes(
        self, code: Code, fixes: List[CodeFix]
    ) -> Code
    
    def should_escalate(
        self, attempt_count: int, error: ExecutionResult
    ) -> bool
    
    async def execute_and_fix(
        self,
        code_content: str,
        language: str = "python",
        filename: str = "main.py",
        dependencies: Optional[List[str]] = None
    ) -> AgentMessage
```

### SandboxEnvironment

```python
class SandboxEnvironment:
    """Docker-based sandbox environment for secure code execution."""
    
    MAX_CPUS = 2
    MAX_MEMORY_MB = 4096
    MAX_DISK_MB = 2048
    MAX_EXECUTION_TIME_SECONDS = 300
    
    async def create_sandbox(
        self, language: str, dependencies: Optional[List[str]] = None
    ) -> Sandbox
    
    async def execute_code(
        self, sandbox: Sandbox, code: Code, timeout: Optional[int] = None
    ) -> ExecutionResult
    
    async def install_dependencies(
        self, sandbox: Sandbox, dependencies: List[str]
    ) -> InstallResult
    
    async def get_resource_usage(
        self, sandbox: Sandbox
    ) -> ResourceUsage
    
    async def cleanup_sandbox(
        self, sandbox: Sandbox
    ) -> None
```

### ErrorAnalyzer

```python
class ErrorAnalyzer:
    """Analyzes execution errors and generates fix suggestions."""
    
    def analyze_error(
        self,
        error_message: str,
        stderr: str,
        exit_code: int,
        code_content: str
    ) -> ErrorAnalysis
```

### FixGenerator

```python
class FixGenerator:
    """Generates code fixes based on error analysis."""
    
    def generate_fixes(
        self,
        analysis: ErrorAnalysis,
        code_content: str,
        filename: str
    ) -> List[CodeFix]
```

## Contributing

### Adding New Error Patterns

To add support for new error types:

1. Add error type to `ErrorType` enum
2. Add pattern to `ErrorAnalyzer.ERROR_PATTERNS`
3. Implement fix strategy in `FixGenerator`
4. Add tests for the new error type

### Adding Language Support

To add support for new languages:

1. Add base image to `SandboxEnvironment.BASE_IMAGES`
2. Add execution command to `SandboxEnvironment.EXECUTION_COMMANDS`
3. Add package manager to `install_dependencies`
4. Test with sample code

## License

This component is part of the Autonomous Software Foundry project.

## Support

For issues, questions, or contributions:
- GitHub Issues: [Project Repository]
- Documentation: [Project Wiki]
- Examples: `examples/reflexion_demo.py`
