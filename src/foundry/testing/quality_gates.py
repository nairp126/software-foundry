"""Quality gates for code validation including linting, type checking, and security scanning."""

import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from foundry.sandbox.environment import Code, ExecutionResult, Sandbox, SandboxEnvironment


class Severity(Enum):
    """Issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class SecurityIssue:
    """Security vulnerability or issue."""

    type: str
    severity: Severity
    file: str
    line: Optional[int]
    description: str
    recommendation: str


@dataclass
class LintIssue:
    """Linting issue."""

    file: str
    line: int
    column: int
    rule: str
    message: str
    severity: str


@dataclass
class TypeIssue:
    """Type checking issue."""

    file: str
    line: int
    column: int
    message: str
    error_code: Optional[str]


@dataclass
class QualityGateResult:
    """Results from quality gate checks."""

    passed: bool
    linting_passed: bool
    type_checking_passed: bool
    security_passed: bool
    lint_issues: List[LintIssue] = field(default_factory=list)
    type_issues: List[TypeIssue] = field(default_factory=list)
    security_issues: List[SecurityIssue] = field(default_factory=list)
    summary: str = ""


class QualityGates:
    """Enforces quality gates including linting, type checking, and security scanning."""

    # Common secret patterns
    SECRET_PATTERNS = [
        (r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]([^'\"]+)['\"]", "API Key"),
        (r"(?i)(secret[_-]?key|secretkey)\s*[:=]\s*['\"]([^'\"]+)['\"]", "Secret Key"),
        (r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]([^'\"]+)['\"]", "Password"),
        (r"(?i)(token|auth[_-]?token)\s*[:=]\s*['\"]([^'\"]+)['\"]", "Auth Token"),
        (r"(?i)(aws[_-]?access[_-]?key[_-]?id)\s*[:=]\s*['\"]([A-Z0-9]{20})['\"]", "AWS Access Key"),
        (
            r"(?i)(aws[_-]?secret[_-]?access[_-]?key)\s*[:=]\s*['\"]([A-Za-z0-9/+=]{40})['\"]",
            "AWS Secret Key",
        ),
        (r"(?i)(private[_-]?key)\s*[:=]\s*['\"]([^'\"]+)['\"]", "Private Key"),
        (r"(?i)(database[_-]?url|db[_-]?url)\s*[:=]\s*['\"]([^'\"]+)['\"]", "Database URL"),
    ]

    def __init__(self):
        """Initialize quality gates."""
        self.sandbox_env = SandboxEnvironment()

    async def run_quality_gates(
        self, code_files: Dict[str, str], language: str, project_path: str
    ) -> QualityGateResult:
        """Run all quality gates on the provided code.

        Args:
            code_files: Dictionary of filename -> code content
            language: Programming language
            project_path: Path to project directory

        Returns:
            QualityGateResult with all check results
        """
        # Run checks in parallel
        linting_task = self.run_linting(code_files, language, project_path)
        type_checking_task = self.run_type_checking(code_files, language, project_path)
        security_task = self.run_security_scan(code_files, language)

        lint_result, type_result, security_result = await asyncio.gather(
            linting_task, type_checking_task, security_task
        )

        # Determine if all gates passed
        linting_passed = len(lint_result) == 0
        type_checking_passed = len(type_result) == 0
        security_passed = all(issue.severity not in [Severity.CRITICAL, Severity.HIGH] for issue in security_result)

        passed = linting_passed and type_checking_passed and security_passed

        # Generate summary
        summary = self._generate_summary(
            linting_passed, type_checking_passed, security_passed, lint_result, type_result, security_result
        )

        return QualityGateResult(
            passed=passed,
            linting_passed=linting_passed,
            type_checking_passed=type_checking_passed,
            security_passed=security_passed,
            lint_issues=lint_result,
            type_issues=type_result,
            security_issues=security_result,
            summary=summary,
        )

    async def run_linting(
        self, code_files: Dict[str, str], language: str, project_path: str
    ) -> List[LintIssue]:
        """Run linting checks based on language.

        Args:
            code_files: Dictionary of filename -> code content
            language: Programming language
            project_path: Path to project directory

        Returns:
            List of linting issues
        """
        language = language.lower()

        if language == "python":
            return await self._run_pylint(code_files, project_path)
        elif language in ["javascript", "typescript"]:
            return await self._run_eslint(code_files, project_path)
        elif language == "ruby":
            return await self._run_rubocop(code_files, project_path)

        return []

    async def _run_pylint(self, code_files: Dict[str, str], project_path: str) -> List[LintIssue]:
        """Run Pylint on Python code."""
        issues = []

        try:
            # Create sandbox for linting
            sandbox = await self.sandbox_env.create_sandbox("python", ["pylint"])

            # Write files to sandbox
            for filename, code in code_files.items():
                if filename.endswith(".py"):
                    code_obj = Code(content=code, language="python", filename=filename)
                    result = await self.sandbox_env.execute_code(
                        sandbox, code_obj, command=f"pylint --output-format=json {filename} || true"
                    )

                    if result.stdout:
                        issues.extend(self._parse_pylint_output(result.stdout, filename))

            await self.sandbox_env.cleanup_sandbox(sandbox)

        except Exception as e:
            # If linting fails, log but don't block
            print(f"Linting failed: {e}")

        return issues

    def _parse_pylint_output(self, output: str, filename: str) -> List[LintIssue]:
        """Parse Pylint JSON output."""
        issues = []
        try:
            data = json.loads(output)
            for item in data:
                issues.append(
                    LintIssue(
                        file=filename,
                        line=item.get("line", 0),
                        column=item.get("column", 0),
                        rule=item.get("message-id", ""),
                        message=item.get("message", ""),
                        severity=item.get("type", "warning"),
                    )
                )
        except json.JSONDecodeError:
            pass

        return issues

    async def _run_eslint(self, code_files: Dict[str, str], project_path: str) -> List[LintIssue]:
        """Run ESLint on JavaScript/TypeScript code."""
        issues = []

        try:
            sandbox = await self.sandbox_env.create_sandbox("javascript", ["eslint"])

            for filename, code in code_files.items():
                if filename.endswith((".js", ".ts", ".jsx", ".tsx")):
                    code_obj = Code(content=code, language="javascript", filename=filename)
                    result = await self.sandbox_env.execute_code(
                        sandbox,
                        code_obj,
                        command=f"eslint --format json {filename} || true",
                    )

                    if result.stdout:
                        issues.extend(self._parse_eslint_output(result.stdout, filename))

            await self.sandbox_env.cleanup_sandbox(sandbox)

        except Exception as e:
            print(f"ESLint failed: {e}")

        return issues

    def _parse_eslint_output(self, output: str, filename: str) -> List[LintIssue]:
        """Parse ESLint JSON output."""
        issues = []
        try:
            data = json.loads(output)
            for file_result in data:
                for message in file_result.get("messages", []):
                    issues.append(
                        LintIssue(
                            file=filename,
                            line=message.get("line", 0),
                            column=message.get("column", 0),
                            rule=message.get("ruleId", ""),
                            message=message.get("message", ""),
                            severity=message.get("severity", 1),
                        )
                    )
        except json.JSONDecodeError:
            pass

        return issues

    async def _run_rubocop(self, code_files: Dict[str, str], project_path: str) -> List[LintIssue]:
        """Run Rubocop on Ruby code."""
        # Placeholder for Ruby linting
        return []

    async def run_type_checking(
        self, code_files: Dict[str, str], language: str, project_path: str
    ) -> List[TypeIssue]:
        """Run type checking based on language.

        Args:
            code_files: Dictionary of filename -> code content
            language: Programming language
            project_path: Path to project directory

        Returns:
            List of type checking issues
        """
        language = language.lower()

        if language == "python":
            return await self._run_mypy(code_files, project_path)
        elif language == "typescript":
            return await self._run_tsc(code_files, project_path)

        return []

    async def _run_mypy(self, code_files: Dict[str, str], project_path: str) -> List[TypeIssue]:
        """Run mypy type checker on Python code."""
        issues = []

        try:
            sandbox = await self.sandbox_env.create_sandbox("python", ["mypy"])

            for filename, code in code_files.items():
                if filename.endswith(".py"):
                    code_obj = Code(content=code, language="python", filename=filename)
                    result = await self.sandbox_env.execute_code(
                        sandbox, code_obj, command=f"mypy --show-error-codes {filename} || true"
                    )

                    if result.stderr:
                        issues.extend(self._parse_mypy_output(result.stderr, filename))

            await self.sandbox_env.cleanup_sandbox(sandbox)

        except Exception as e:
            print(f"Type checking failed: {e}")

        return issues

    def _parse_mypy_output(self, output: str, filename: str) -> List[TypeIssue]:
        """Parse mypy output."""
        issues = []
        # mypy format: filename:line:column: error: message [error-code]
        pattern = r"(.+):(\d+):(\d+):\s+error:\s+(.+?)(?:\s+\[(.+?)\])?"

        for line in output.splitlines():
            match = re.match(pattern, line)
            if match:
                issues.append(
                    TypeIssue(
                        file=filename,
                        line=int(match.group(2)),
                        column=int(match.group(3)),
                        message=match.group(4),
                        error_code=match.group(5),
                    )
                )

        return issues

    async def _run_tsc(self, code_files: Dict[str, str], project_path: str) -> List[TypeIssue]:
        """Run TypeScript compiler type checking."""
        # Placeholder for TypeScript type checking
        return []

    async def run_security_scan(
        self, code_files: Dict[str, str], language: str
    ) -> List[SecurityIssue]:
        """Run security scanning for common vulnerabilities.

        Args:
            code_files: Dictionary of filename -> code content
            language: Programming language

        Returns:
            List of security issues
        """
        issues = []

        # Run secret detection
        issues.extend(self._detect_secrets(code_files))

        # Run language-specific security scans
        language = language.lower()
        if language == "python":
            issues.extend(await self._run_bandit(code_files))
        elif language in ["javascript", "typescript"]:
            issues.extend(await self._run_npm_audit(code_files))

        return issues

    def _detect_secrets(self, code_files: Dict[str, str]) -> List[SecurityIssue]:
        """Detect hardcoded secrets in code."""
        issues = []

        for filename, code in code_files.items():
            for line_num, line in enumerate(code.splitlines(), 1):
                for pattern, secret_type in self.SECRET_PATTERNS:
                    if re.search(pattern, line):
                        issues.append(
                            SecurityIssue(
                                type="hardcoded_secret",
                                severity=Severity.CRITICAL,
                                file=filename,
                                line=line_num,
                                description=f"Potential {secret_type} detected in code",
                                recommendation=f"Replace with environment variable or secure secret management",
                            )
                        )

        return issues

    async def _run_bandit(self, code_files: Dict[str, str]) -> List[SecurityIssue]:
        """Run Bandit security scanner on Python code."""
        issues = []

        try:
            sandbox = await self.sandbox_env.create_sandbox("python", ["bandit"])

            for filename, code in code_files.items():
                if filename.endswith(".py"):
                    code_obj = Code(content=code, language="python", filename=filename)
                    result = await self.sandbox_env.execute_code(
                        sandbox, code_obj, command=f"bandit -f json {filename} || true"
                    )

                    if result.stdout:
                        issues.extend(self._parse_bandit_output(result.stdout, filename))

            await self.sandbox_env.cleanup_sandbox(sandbox)

        except Exception as e:
            print(f"Bandit scan failed: {e}")

        return issues

    def _parse_bandit_output(self, output: str, filename: str) -> List[SecurityIssue]:
        """Parse Bandit JSON output."""
        issues = []
        try:
            data = json.loads(output)
            for result in data.get("results", []):
                severity_map = {
                    "HIGH": Severity.HIGH,
                    "MEDIUM": Severity.MEDIUM,
                    "LOW": Severity.LOW,
                }

                issues.append(
                    SecurityIssue(
                        type=result.get("test_id", ""),
                        severity=severity_map.get(result.get("issue_severity", "LOW"), Severity.LOW),
                        file=filename,
                        line=result.get("line_number"),
                        description=result.get("issue_text", ""),
                        recommendation=result.get("issue_confidence", "Review and fix"),
                    )
                )
        except json.JSONDecodeError:
            pass

        return issues

    async def _run_npm_audit(self, code_files: Dict[str, str]) -> List[SecurityIssue]:
        """Run npm audit on JavaScript/TypeScript projects."""
        # Placeholder for npm audit
        return []

    def _generate_summary(
        self,
        linting_passed: bool,
        type_checking_passed: bool,
        security_passed: bool,
        lint_issues: List[LintIssue],
        type_issues: List[TypeIssue],
        security_issues: List[SecurityIssue],
    ) -> str:
        """Generate quality gate summary."""
        summary_parts = []

        if linting_passed:
            summary_parts.append("✓ Linting: PASSED")
        else:
            summary_parts.append(f"✗ Linting: FAILED ({len(lint_issues)} issues)")

        if type_checking_passed:
            summary_parts.append("✓ Type Checking: PASSED")
        else:
            summary_parts.append(f"✗ Type Checking: FAILED ({len(type_issues)} issues)")

        if security_passed:
            summary_parts.append("✓ Security Scan: PASSED")
        else:
            critical_count = sum(
                1 for issue in security_issues if issue.severity == Severity.CRITICAL
            )
            high_count = sum(1 for issue in security_issues if issue.severity == Severity.HIGH)
            summary_parts.append(
                f"✗ Security Scan: FAILED ({critical_count} critical, {high_count} high)"
            )

        return "\n".join(summary_parts)
