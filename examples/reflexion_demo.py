"""
Demo script for the Reflexion Engine.

This demonstrates the Execute → Analyze → Fix → Retry → Escalate workflow.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from foundry.agents.reflexion import ReflexionEngine
from foundry.agents.base import AgentType, MessageType


async def demo_successful_execution():
    """Demo: Code that executes successfully on first try."""
    print("\n" + "=" * 80)
    print("DEMO 1: Successful Execution (No Fixes Needed)")
    print("=" * 80)
    
    engine = ReflexionEngine()
    
    code = '''
def greet(name):
    return f"Hello, {name}!"

result = greet("World")
print(result)
'''
    
    print("\nCode to execute:")
    print(code)
    print("\nExecuting...")
    
    message = await engine.execute_and_fix(
        code_content=code,
        language="python",
        filename="greet.py"
    )
    
    print(f"\nResult: {message.payload['status']}")
    if message.payload['status'] == 'success':
        print(f"Attempts: {message.payload['result']['attempts']}")
        print(f"Execution time: {message.payload['result']['execution_time']:.2f}s")
        print(f"Output:\n{message.payload['result']['stdout']}")


async def demo_name_error_fix():
    """Demo: Code with NameError that gets fixed automatically."""
    print("\n" + "=" * 80)
    print("DEMO 2: Automatic Fix for NameError")
    print("=" * 80)
    
    engine = ReflexionEngine()
    
    code = '''
# This code has a NameError - variable 'x' is not defined
print(f"The value is: {x}")
'''
    
    print("\nCode to execute (has NameError):")
    print(code)
    print("\nExecuting with automatic fix...")
    
    message = await engine.execute_and_fix(
        code_content=code,
        language="python",
        filename="name_error.py"
    )
    
    print(f"\nResult: {message.payload['status']}")
    if 'execution_history' in message.payload:
        print(f"Total attempts: {len(message.payload['execution_history'])}")
        for i, attempt in enumerate(message.payload['execution_history'], 1):
            print(f"  Attempt {i}: {'✓ Success' if attempt['success'] else '✗ Failed'}")


async def demo_syntax_error_fix():
    """Demo: Code with syntax error that gets fixed."""
    print("\n" + "=" * 80)
    print("DEMO 3: Automatic Fix for Syntax Error")
    print("=" * 80)
    
    engine = ReflexionEngine()
    
    code = '''
# This code has a syntax error - using = instead of ==
if x = 5:
    print("x is 5")
'''
    
    print("\nCode to execute (has SyntaxError):")
    print(code)
    print("\nExecuting with automatic fix...")
    
    message = await engine.execute_and_fix(
        code_content=code,
        language="python",
        filename="syntax_error.py"
    )
    
    print(f"\nResult: {message.payload['status']}")
    if 'execution_history' in message.payload:
        print(f"Total attempts: {len(message.payload['execution_history'])}")


async def demo_import_error_fix():
    """Demo: Code with import error."""
    print("\n" + "=" * 80)
    print("DEMO 4: Import Error Detection")
    print("=" * 80)
    
    engine = ReflexionEngine()
    
    code = '''
import nonexistent_module

result = nonexistent_module.do_something()
print(result)
'''
    
    print("\nCode to execute (has ImportError):")
    print(code)
    print("\nExecuting...")
    
    message = await engine.execute_and_fix(
        code_content=code,
        language="python",
        filename="import_error.py"
    )
    
    print(f"\nResult: {message.payload['status']}")
    if message.payload['status'] == 'escalated':
        print("Error escalated to human intervention (as expected for missing modules)")
        if 'error_analysis' in message.payload:
            analysis = message.payload['error_analysis']
            print(f"Error type: {analysis['error_type']}")
            print(f"Root cause: {analysis['root_cause']}")


async def demo_error_analysis():
    """Demo: Error analysis capabilities."""
    print("\n" + "=" * 80)
    print("DEMO 5: Error Analysis Capabilities")
    print("=" * 80)
    
    from foundry.sandbox.environment import ExecutionResult, ResourceUsage
    from foundry.sandbox.error_analysis import ErrorAnalyzer
    
    analyzer = ErrorAnalyzer()
    
    # Simulate different error types
    errors = [
        {
            "name": "NameError",
            "stderr": "NameError: name 'undefined_var' is not defined",
            "code": "print(undefined_var)"
        },
        {
            "name": "TypeError",
            "stderr": "TypeError: can only concatenate str (not 'int') to str",
            "code": "result = 'text' + 5"
        },
        {
            "name": "IndexError",
            "stderr": "IndexError: list index out of range",
            "code": "items = [1, 2, 3]\nprint(items[10])"
        },
    ]
    
    for error in errors:
        print(f"\n{error['name']}:")
        analysis = analyzer.analyze_error(
            error_message=error['stderr'],
            stderr=error['stderr'],
            exit_code=1,
            code_content=error['code']
        )
        
        print(f"  Error Type: {analysis.error_type}")
        print(f"  Severity: {analysis.severity}")
        print(f"  Root Cause: {analysis.root_cause}")
        print(f"  Suggested Fixes:")
        for fix in analysis.suggested_fixes[:2]:  # Show first 2 suggestions
            print(f"    - {fix}")


async def demo_sandbox_security():
    """Demo: Sandbox security features."""
    print("\n" + "=" * 80)
    print("DEMO 6: Sandbox Security Features")
    print("=" * 80)
    
    from foundry.sandbox.environment import SandboxEnvironment, Code
    
    env = SandboxEnvironment()
    
    print("\nSecurity Features:")
    print(f"  - Max CPUs: {env.MAX_CPUS}")
    print(f"  - Max Memory: {env.MAX_MEMORY_MB} MB")
    print(f"  - Max Disk: {env.MAX_DISK_MB} MB")
    print(f"  - Max Execution Time: {env.MAX_EXECUTION_TIME_SECONDS} seconds")
    print("\n  - Read-only root filesystem")
    print("  - Network isolation")
    print("  - Dropped capabilities")
    print("  - No privilege escalation")
    
    print("\nCreating secure sandbox...")
    sandbox = await env.create_sandbox(language="python")
    print(f"Sandbox created: {sandbox.sandbox_id}")
    print(f"Status: {sandbox.status}")
    
    # Test timeout
    print("\nTesting execution timeout (1 second limit)...")
    code = Code(
        content="import time\ntime.sleep(2)",
        language="python",
        filename="timeout_test.py"
    )
    
    result = await env.execute_code(sandbox, code, timeout=1)
    print(f"Result: {'Timeout detected ✓' if not result.success else 'No timeout'}")
    
    await env.cleanup_sandbox(sandbox)
    print("Sandbox cleaned up")


async def main():
    """Run all demos."""
    print("\n" + "=" * 80)
    print("REFLEXION ENGINE DEMONSTRATION")
    print("Autonomous Error Detection and Correction System")
    print("=" * 80)
    
    try:
        # Run demos
        await demo_successful_execution()
        await demo_name_error_fix()
        await demo_syntax_error_fix()
        await demo_import_error_fix()
        await demo_error_analysis()
        await demo_sandbox_security()
        
        print("\n" + "=" * 80)
        print("DEMONSTRATION COMPLETE")
        print("=" * 80)
        print("\nKey Features Demonstrated:")
        print("  ✓ Automatic error detection")
        print("  ✓ Root cause analysis")
        print("  ✓ Automatic fix generation")
        print("  ✓ Retry logic with max attempts")
        print("  ✓ Escalation to human intervention")
        print("  ✓ Secure sandboxed execution")
        print("  ✓ Resource limits and timeouts")
        
    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
