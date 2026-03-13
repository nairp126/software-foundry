"""Tests for automated test generation."""

import pytest
from foundry.testing.test_generator import TestGenerator, TestFramework, CoverageAnalysis


class TestTestGenerator:
    """Test suite for TestGenerator."""

    @pytest.fixture
    def generator(self):
        """Create test generator instance."""
        return TestGenerator()

    def test_select_framework_python(self, generator):
        """Test framework selection for Python."""
        framework = generator.select_framework("python")
        assert framework == TestFramework.PYTEST

    def test_select_framework_javascript(self, generator):
        """Test framework selection for JavaScript."""
        framework = generator.select_framework("javascript")
        assert framework == TestFramework.JEST

    def test_select_framework_typescript(self, generator):
        """Test framework selection for TypeScript."""
        framework = generator.select_framework("typescript")
        assert framework == TestFramework.JEST

    def test_select_framework_with_vitest_stack(self, generator):
        """Test framework selection with Vitest in tech stack."""
        tech_stack = {"build_tool": "vite", "test_framework": "vitest"}
        framework = generator.select_framework("typescript", tech_stack)
        assert framework == TestFramework.VITEST

    def test_get_test_filename_pytest(self, generator):
        """Test filename generation for pytest."""
        filename = generator.get_test_filename("calculator.py", TestFramework.PYTEST)
        assert filename == "test_calculator.py"

    def test_get_test_filename_jest(self, generator):
        """Test filename generation for Jest."""
        filename = generator.get_test_filename("calculator.ts", TestFramework.JEST)
        assert filename == "calculator.test.ts"

    def test_get_test_filename_junit(self, generator):
        """Test filename generation for JUnit."""
        filename = generator.get_test_filename("Calculator.java", TestFramework.JUNIT)
        assert filename == "CalculatorTest.java"

    @pytest.mark.asyncio
    async def test_generate_unit_tests_python(self, generator):
        """Test unit test generation for Python code."""
        code = """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
"""
        test_code = await generator.generate_unit_tests(code, "calculator.py", "python")
        assert test_code
        assert isinstance(test_code, str)
        assert len(test_code) > 0


    @pytest.mark.asyncio
    async def test_analyze_coverage(self, generator):
        """Test coverage analysis."""
        source_files = {
            "calculator.py": """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b
"""
        }
        
        test_files = {
            "test_calculator.py": """
def test_add():
    assert add(1, 2) == 3

def test_subtract():
    assert subtract(5, 3) == 2
"""
        }
        
        coverage = await generator.analyze_coverage(source_files, test_files, "python")
        assert isinstance(coverage, CoverageAnalysis)
        assert coverage.total_lines > 0
        assert coverage.coverage_percentage >= 0
        assert coverage.coverage_percentage <= 100

    def test_extract_code_from_response_with_markdown(self, generator):
        """Test code extraction from markdown response."""
        response = """```python
def test_example():
    assert True
```"""
        code = generator._extract_code_from_response(response)
        assert "def test_example():" in code
        assert "```" not in code

    def test_extract_code_from_response_plain(self, generator):
        """Test code extraction from plain response."""
        response = "def test_example():\n    assert True"
        code = generator._extract_code_from_response(response)
        assert code == response.strip()
