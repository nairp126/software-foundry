"""Unit tests for the language_guards module (Requirement 8)."""

import pytest
from foundry.utils.language_guards import detect_language_mismatch, recover_prompt

# ---------------------------------------------------------------------------
# Sample code snippets for mismatch detection tests
# ---------------------------------------------------------------------------

PYTHON_CODE = """\
from typing import List

def add(a: int, b: int) -> int:
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y

if __name__ == "__main__":
    print(add(1, 2))
"""

JAVASCRIPT_CODE = """\
const express = require('express');
const app = express();

const add = (a, b) => {
    return a + b;
};

module.exports = { add };
console.log(add(1, 2));
"""

TYPESCRIPT_CODE = """\
interface Calculator {
    add(a: number, b: number): number;
}

const calc: Calculator = {
    add: (a: number, b: number): number => a + b,
};

export default calc;
"""

JAVA_CODE = """\
import java.util.List;
import java.util.ArrayList;

public class Calculator {
    private int value;

    public int add(int a, int b) {
        return a + b;
    }

    @Override
    public String toString() {
        return "Calculator";
    }
}
"""


class TestDetectLanguageMismatch:
    """Tests for detect_language_mismatch() — Requirement 8.2."""

    # --- No mismatch (code matches expected language) ---

    def test_python_code_matches_python(self):
        assert detect_language_mismatch(PYTHON_CODE, "python") is False

    def test_javascript_code_matches_javascript(self):
        assert detect_language_mismatch(JAVASCRIPT_CODE, "javascript") is False

    def test_typescript_code_matches_typescript(self):
        assert detect_language_mismatch(TYPESCRIPT_CODE, "typescript") is False

    def test_java_code_matches_java(self):
        assert detect_language_mismatch(JAVA_CODE, "java") is False

    # --- Mismatch detected ---

    def test_javascript_code_mismatches_python(self):
        assert detect_language_mismatch(JAVASCRIPT_CODE, "python") is True

    def test_java_code_mismatches_python(self):
        assert detect_language_mismatch(JAVA_CODE, "python") is True

    def test_python_code_mismatches_javascript(self):
        assert detect_language_mismatch(PYTHON_CODE, "javascript") is True

    def test_python_code_mismatches_java(self):
        assert detect_language_mismatch(PYTHON_CODE, "java") is True

    # --- Edge cases ---

    def test_empty_code_returns_false(self):
        """Empty code has no signal — should not report mismatch."""
        assert detect_language_mismatch("", "python") is False

    def test_whitespace_only_returns_false(self):
        assert detect_language_mismatch("   \n\t  ", "python") is False

    def test_case_insensitive_expected_language(self):
        """Expected language comparison is case-insensitive."""
        assert detect_language_mismatch(PYTHON_CODE, "PYTHON") is False

    def test_no_hard_coded_python_blocking(self):
        """Guards must not block non-Python code when expected language is non-Python.
        Requirement 8.4: no hard-coded blocking gates for non-Python.
        """
        # JS code with expected=javascript should NOT be flagged as mismatch
        assert detect_language_mismatch(JAVASCRIPT_CODE, "javascript") is False
        # Java code with expected=java should NOT be flagged as mismatch
        assert detect_language_mismatch(JAVA_CODE, "java") is False


class TestRecoverPrompt:
    """Tests for recover_prompt() — Requirement 8.3."""

    @pytest.mark.parametrize("target_language", ["python", "javascript", "typescript", "java"])
    def test_returns_non_empty_string(self, target_language):
        """recover_prompt always returns a non-empty string for all supported languages."""
        result = recover_prompt(
            filename=f"app.{target_language[:2]}",
            dirty_code="wrong code here",
            target_language=target_language,
            architecture="Simple REST API",
        )
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_prompt_mentions_target_language(self):
        """The prompt references the target language."""
        result = recover_prompt(
            filename="app.js",
            dirty_code="def wrong(): pass",
            target_language="javascript",
            architecture="Express REST API",
        )
        assert "javascript" in result.lower() or "JavaScript" in result

    def test_prompt_mentions_filename(self):
        """The prompt references the filename."""
        result = recover_prompt(
            filename="Calculator.java",
            dirty_code="const x = 1;",
            target_language="java",
            architecture="Spring Boot service",
        )
        assert "Calculator.java" in result

    def test_prompt_mentions_architecture(self):
        """The prompt includes the architecture context."""
        arch = "FastAPI microservice with PostgreSQL"
        result = recover_prompt(
            filename="main.py",
            dirty_code="const x = 1;",
            target_language="python",
            architecture=arch,
        )
        assert arch in result

    def test_prompt_for_unknown_language_still_non_empty(self):
        """Even for an unknown language, recover_prompt returns a non-empty string
        (falls back to Python config)."""
        result = recover_prompt(
            filename="app.xyz",
            dirty_code="some code",
            target_language="cobol",
            architecture="Legacy system",
        )
        assert isinstance(result, str)
        assert len(result.strip()) > 0
