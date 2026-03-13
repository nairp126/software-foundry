"""Demo of automated testing and quality assurance features."""

import asyncio
from foundry.testing.test_generator import TestGenerator, TestFramework
from foundry.testing.quality_gates import QualityGates


async def demo_test_generation():
    """Demonstrate automated test generation."""
    print("=" * 60)
    print("DEMO: Automated Test Generation")
    print("=" * 60)
    
    # Sample Python code
    sample_code = """
def calculate_total(items):
    '''Calculate total price of items.'''
    return sum(item['price'] * item['quantity'] for item in items)

def apply_discount(total, discount_percent):
    '''Apply discount to total.'''
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount must be between 0 and 100")
    return total * (1 - discount_percent / 100)
"""
    
    print("\nSource Code:")
    print(sample_code)
    
    # Initialize test generator
    generator = TestGenerator()
    
    # Select framework
    framework = generator.select_framework("python")
    print(f"\nSelected Test Framework: {framework.value}")
    
    # Generate tests
    print("\nGenerating unit tests...")
    test_code = await generator.generate_unit_tests(
        sample_code, "calculator.py", "python", framework
    )
    
    print("\nGenerated Test Code:")
    print(test_code[:500] + "..." if len(test_code) > 500 else test_code)
    
    # Get test filename
    test_filename = generator.get_test_filename("calculator.py", framework)
    print(f"\nTest Filename: {test_filename}")


async def demo_quality_gates():
    """Demonstrate quality gates."""
    print("\n" + "=" * 60)
    print("DEMO: Quality Gates")
    print("=" * 60)
    
    # Sample code with issues
    code_with_issues = {
        "config.py": """
# Configuration file with hardcoded secrets (BAD!)
API_KEY = "sk-1234567890abcdef1234567890abcdef"
DATABASE_URL = "postgresql://user:password@localhost/db"

def get_config():
    return {
        'api_key': API_KEY,
        'db_url': DATABASE_URL
    }
""",
        "main.py": """
def process_data(data):
    # Missing error handling
    result = data['value'] * 2
    return result
"""
    }
    
    print("\nCode Files:")
    for filename, code in code_with_issues.items():
        print(f"\n{filename}:")
        print(code[:200] + "..." if len(code) > 200 else code)
    
    # Initialize quality gates
    quality_gates = QualityGates()
    
    # Run security scan
    print("\n" + "-" * 60)
    print("Running Security Scan...")
    print("-" * 60)
    security_issues = await quality_gates.run_security_scan(code_with_issues, "python")
    
    print(f"\nFound {len(security_issues)} security issues:")
    for issue in security_issues[:3]:  # Show first 3
        print(f"  - [{issue.severity.value.upper()}] {issue.description}")
        print(f"    File: {issue.file}, Line: {issue.line}")
        print(f"    Recommendation: {issue.recommendation}")
    
    # Clean code example
    clean_code = {
        "config.py": """
import os

# Proper configuration using environment variables
API_KEY = os.environ.get("API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_config():
    return {
        'api_key': API_KEY,
        'db_url': DATABASE_URL
    }
"""
    }
    
    print("\n" + "-" * 60)
    print("Scanning Clean Code...")
    print("-" * 60)
    clean_issues = await quality_gates.run_security_scan(clean_code, "python")
    print(f"\nFound {len(clean_issues)} security issues in clean code ✓")


async def demo_coverage_analysis():
    """Demonstrate coverage analysis."""
    print("\n" + "=" * 60)
    print("DEMO: Coverage Analysis")
    print("=" * 60)
    
    source_files = {
        "math_utils.py": """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
"""
    }
    
    test_files = {
        "test_math_utils.py": """
def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2

def test_multiply():
    assert multiply(4, 5) == 20
"""
    }
    
    print("\nSource Files:")
    for name, code in source_files.items():
        print(f"{name}: {len(code.splitlines())} lines")
    
    print("\nTest Files:")
    for name, code in test_files.items():
        print(f"{name}: {len(code.splitlines())} lines")
    
    generator = TestGenerator()
    
    print("\nAnalyzing coverage...")
    coverage = await generator.analyze_coverage(source_files, test_files, "python")
    
    print(f"\nCoverage Results:")
    print(f"  Total Lines: {coverage.total_lines}")
    print(f"  Covered Lines: {coverage.covered_lines}")
    print(f"  Coverage: {coverage.coverage_percentage:.1f}%")
    print(f"  Meets 80% Threshold: {'✓ Yes' if coverage.meets_threshold else '✗ No'}")
    
    if coverage.uncovered_files:
        print(f"  Uncovered Files: {', '.join(coverage.uncovered_files)}")


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("AUTONOMOUS SOFTWARE FOUNDRY")
    print("Testing & Quality Assurance Demo")
    print("=" * 60)
    
    try:
        await demo_test_generation()
        await demo_quality_gates()
        await demo_coverage_analysis()
        
        print("\n" + "=" * 60)
        print("Demo Complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
