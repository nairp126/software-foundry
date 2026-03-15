"""Automated test generation for generated code."""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from foundry.llm.base import BaseLLMProvider, LLMMessage
from foundry.llm.factory import LLMProviderFactory
from foundry.config import settings


class TestFramework(Enum):
    """Supported test frameworks by language."""

    PYTEST = "pytest"


@dataclass
class CoverageAnalysis:
    """Code coverage analysis results."""

    total_lines: int
    covered_lines: int
    coverage_percentage: float
    uncovered_files: List[str]
    meets_threshold: bool


class TestGenerator:
    """Generates automated tests for code with coverage analysis."""

    FRAMEWORK_MAP = {
        "python": TestFramework.PYTEST
    }

    COVERAGE_THRESHOLD = 80.0

    def __init__(self, model_name: Optional[str] = None):
        """Initialize test generator with LLM provider."""
        model_name = model_name or settings.ollama_model_name
        self.llm: BaseLLMProvider = LLMProviderFactory.create_provider("ollama", model_name)

    def select_framework(self, language: str, tech_stack: Optional[Dict] = None) -> TestFramework:
        """Select appropriate test framework based on language and tech stack.

        Args:
            language: Programming language (python, javascript, typescript, java)
            tech_stack: Optional technology stack details

        Returns:
            TestFramework enum value
        """
        language = language.lower()

        # Check tech stack for specific preferences
        if tech_stack:
            if "vite" in str(tech_stack).lower() or "vitest" in str(tech_stack).lower():
                return TestFramework.VITEST
            if "mocha" in str(tech_stack).lower():
                return TestFramework.MOCHA

        # Default framework selection
        return self.FRAMEWORK_MAP.get(language, TestFramework.PYTEST)

    async def generate_unit_tests(
        self, code: str, filename: str, language: str, framework: Optional[TestFramework] = None
    ) -> str:
        """Generate unit tests for the given code.

        Args:
            code: Source code to generate tests for
            filename: Name of the source file
            language: Programming language
            framework: Optional specific test framework to use

        Returns:
            Generated test code as string
        """
        if framework is None:
            framework = self.select_framework(language)

        prompt = self._build_test_generation_prompt(code, filename, language, framework)

        messages = [LLMMessage(role="user", content=prompt)]
        response = await self.llm.generate(messages)
        test_code = self._extract_code_from_response(response.content)

        return test_code

    def _build_test_generation_prompt(
        self, code: str, filename: str, language: str, framework: TestFramework
    ) -> str:
        """Build prompt for test generation."""
        framework_instructions = self._get_framework_instructions(framework)

        return f"""Generate comprehensive unit tests for the following {language} code.

Source file: {filename}

Code:
```{language}
{code}
```

Requirements:
1. Use {framework.value} testing framework
2. Achieve minimum 80% code coverage
3. Test all public functions/methods
4. Include edge cases and error conditions
5. Use descriptive test names
6. Add appropriate assertions
7. Mock external dependencies

{framework_instructions}

Generate ONLY the test code without explanations. Use proper {language} syntax."""

    def _get_framework_instructions(self, framework: TestFramework) -> str:
        """Get framework-specific instructions."""
        instructions = {
            TestFramework.PYTEST: """
Framework-specific guidelines:
- Use pytest fixtures for setup/teardown
- Use pytest.mark for test categorization
- Use pytest.raises for exception testing
- Follow pytest naming conventions (test_*.py)
""",
        }
        return instructions.get(framework, "")

    def _extract_code_from_response(self, response: str) -> str:
        """Extract code from LLM response."""
        # Try to extract code from markdown code blocks
        code_block_pattern = r"```(?:\w+)?\n(.*?)```"
        matches = re.findall(code_block_pattern, response, re.DOTALL)

        if matches:
            return matches[0].strip()

        # If no code blocks, return the whole response
        return response.strip()

    async def analyze_coverage(
        self, source_files: Dict[str, str], test_files: Dict[str, str], language: str
    ) -> CoverageAnalysis:
        """Analyze code coverage for generated tests.

        Args:
            source_files: Dictionary of source filename -> code
            test_files: Dictionary of test filename -> test code
            language: Programming language

        Returns:
            CoverageAnalysis with coverage metrics
        """
        # Calculate basic coverage metrics
        total_lines = sum(len(code.splitlines()) for code in source_files.values())

        # Use LLM to estimate coverage
        prompt = self._build_coverage_analysis_prompt(source_files, test_files, language)
        messages = [LLMMessage(role="user", content=prompt)]
        response = await self.llm.generate(messages)

        coverage_data = self._parse_coverage_response(response.content, total_lines)

        return CoverageAnalysis(
            total_lines=total_lines,
            covered_lines=coverage_data["covered_lines"],
            coverage_percentage=coverage_data["percentage"],
            uncovered_files=coverage_data["uncovered_files"],
            meets_threshold=coverage_data["percentage"] >= self.COVERAGE_THRESHOLD,
        )

    def _build_coverage_analysis_prompt(
        self, source_files: Dict[str, str], test_files: Dict[str, str], language: str
    ) -> str:
        """Build prompt for coverage analysis."""
        source_summary = "\n\n".join(
            [f"File: {name}\n{code[:500]}..." for name, code in source_files.items()]
        )
        test_summary = "\n\n".join(
            [f"Test: {name}\n{code[:500]}..." for name, code in test_files.items()]
        )

        return f"""Analyze the code coverage of the following {language} tests.

Source Files:
{source_summary}

Test Files:
{test_summary}

Provide coverage analysis in this format:
COVERAGE: <percentage>%
COVERED_LINES: <number>
UNCOVERED_FILES: <comma-separated list or "none">

Be realistic about coverage estimation."""

    def _parse_coverage_response(self, response: str, total_lines: int) -> Dict:
        """Parse coverage analysis response."""
        # Extract coverage percentage
        coverage_match = re.search(r"COVERAGE:\s*(\d+(?:\.\d+)?)", response)
        percentage = float(coverage_match.group(1)) if coverage_match else 75.0

        # Extract covered lines
        covered_match = re.search(r"COVERED_LINES:\s*(\d+)", response)
        covered_lines = int(covered_match.group(1)) if covered_match else int(
            total_lines * percentage / 100
        )

        # Extract uncovered files
        uncovered_match = re.search(r"UNCOVERED_FILES:\s*(.+)", response)
        uncovered_text = uncovered_match.group(1).strip() if uncovered_match else "none"
        uncovered_files = (
            [] if uncovered_text.lower() == "none" else [f.strip() for f in uncovered_text.split(",")]
        )

        return {
            "percentage": percentage,
            "covered_lines": covered_lines,
            "uncovered_files": uncovered_files,
        }

    def get_test_filename(self, source_filename: str, framework: TestFramework) -> str:
        """Generate appropriate test filename based on framework conventions.

        Args:
            source_filename: Original source file name
            framework: Test framework being used

        Returns:
            Test filename following framework conventions
        """
        path = Path(source_filename)
        stem = path.stem
        suffix = path.suffix

        if framework in [TestFramework.PYTEST]:
            return f"test_{stem}{suffix}"
        elif framework in [TestFramework.JEST, TestFramework.VITEST, TestFramework.MOCHA]:
            return f"{stem}.test{suffix}"
        elif framework == TestFramework.JUNIT:
            return f"{stem}Test{suffix}"

        return f"test_{stem}{suffix}"
