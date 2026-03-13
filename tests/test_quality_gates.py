"""Tests for quality gates."""

import pytest
from foundry.testing.quality_gates import (
    QualityGates,
    QualityGateResult,
    SecurityIssue,
    Severity,
    LintIssue,
    TypeIssue,
)


class TestQualityGates:
    """Test suite for QualityGates."""

    @pytest.fixture
    def quality_gates(self):
        """Create quality gates instance."""
        return QualityGates()

    def test_detect_secrets_api_key(self, quality_gates):
        """Test detection of hardcoded API keys."""
        code_files = {
            "config.py": 'API_KEY = "sk-1234567890abcdef1234567890abcdef"'
        }
        issues = quality_gates._detect_secrets(code_files)
        assert len(issues) > 0
        assert any(issue.type == "hardcoded_secret" for issue in issues)
        assert any(issue.severity == Severity.CRITICAL for issue in issues)

    def test_detect_secrets_password(self, quality_gates):
        """Test detection of hardcoded passwords."""
        code_files = {
            "auth.py": 'password = "MySecretPassword123"'
        }
        issues = quality_gates._detect_secrets(code_files)
        assert len(issues) > 0
        assert any("Password" in issue.description for issue in issues)

    def test_detect_secrets_aws_keys(self, quality_gates):
        """Test detection of AWS credentials."""
        code_files = {
            "aws_config.py": 'AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"'
        }
        issues = quality_gates._detect_secrets(code_files)
        assert len(issues) > 0

    def test_detect_secrets_clean_code(self, quality_gates):
        """Test that clean code produces no secret issues."""
        code_files = {
            "config.py": """
import os

API_KEY = os.environ.get("API_KEY")
PASSWORD = os.getenv("PASSWORD")
"""
        }
        issues = quality_gates._detect_secrets(code_files)
        assert len(issues) == 0

    def test_parse_pylint_output(self, quality_gates):
        """Test parsing of Pylint JSON output."""
        pylint_output = """[
            {
                "line": 10,
                "column": 5,
                "message-id": "C0103",
                "message": "Variable name doesn't conform to snake_case",
                "type": "convention"
            }
        ]"""
        issues = quality_gates._parse_pylint_output(pylint_output, "test.py")
        assert len(issues) == 1
        assert issues[0].file == "test.py"
        assert issues[0].line == 10


    def test_parse_eslint_output(self, quality_gates):
        """Test parsing of ESLint JSON output."""
        eslint_output = """[
            {
                "messages": [
                    {
                        "line": 5,
                        "column": 10,
                        "ruleId": "no-unused-vars",
                        "message": "Variable is defined but never used",
                        "severity": 2
                    }
                ]
            }
        ]"""
        issues = quality_gates._parse_eslint_output(eslint_output, "test.js")
        assert len(issues) == 1
        assert issues[0].rule == "no-unused-vars"

    def test_parse_mypy_output(self, quality_gates):
        """Test parsing of mypy output."""
        mypy_output = """test.py:15:10: error: Incompatible types [assignment]"""
        issues = quality_gates._parse_mypy_output(mypy_output, "test.py")
        assert len(issues) == 1
        assert issues[0].line == 15
        assert issues[0].column == 10

    def test_parse_bandit_output(self, quality_gates):
        """Test parsing of Bandit JSON output."""
        bandit_output = """{
            "results": [
                {
                    "test_id": "B201",
                    "issue_severity": "HIGH",
                    "line_number": 20,
                    "issue_text": "Use of exec detected",
                    "issue_confidence": "HIGH"
                }
            ]
        }"""
        issues = quality_gates._parse_bandit_output(bandit_output, "test.py")
        assert len(issues) == 1
        assert issues[0].severity == Severity.HIGH
        assert issues[0].line == 20

    def test_generate_summary_all_passed(self, quality_gates):
        """Test summary generation when all gates pass."""
        summary = quality_gates._generate_summary(True, True, True, [], [], [])
        assert "✓ Linting: PASSED" in summary
        assert "✓ Type Checking: PASSED" in summary
        assert "✓ Security Scan: PASSED" in summary

    def test_generate_summary_with_failures(self, quality_gates):
        """Test summary generation with failures."""
        lint_issues = [LintIssue("test.py", 1, 1, "rule", "message", "error")]
        security_issues = [
            SecurityIssue("secret", Severity.CRITICAL, "test.py", 1, "desc", "rec")
        ]
        summary = quality_gates._generate_summary(
            False, True, False, lint_issues, [], security_issues
        )
        assert "✗ Linting: FAILED" in summary
        assert "✓ Type Checking: PASSED" in summary
        assert "✗ Security Scan: FAILED" in summary
        assert "1 critical" in summary

    @pytest.mark.asyncio
    async def test_run_quality_gates_integration(self, quality_gates):
        """Test full quality gates integration."""
        code_files = {
            "example.py": """
def calculate(x, y):
    return x + y
"""
        }
        result = await quality_gates.run_quality_gates(code_files, "python", "/tmp/test")
        assert isinstance(result, QualityGateResult)
        assert isinstance(result.passed, bool)
        assert isinstance(result.summary, str)
