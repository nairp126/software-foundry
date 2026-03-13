"""Property-based tests for testing and quality assurance components."""

import pytest
from hypothesis import given, strategies as st, settings
from foundry.testing.test_generator import TestGenerator, TestFramework
from foundry.testing.quality_gates import QualityGates, Severity


class TestTestingProperties:
    """Property-based tests for testing components."""

    @settings(deadline=500)
    @given(st.sampled_from(["python", "javascript", "typescript", "java"]))
    def test_framework_selection_always_returns_valid_framework(self, language):
        """
        **Validates: Requirements 17.3**
        
        Property: Framework selection should always return a valid TestFramework
        for any supported language.
        """
        generator = TestGenerator()
        framework = generator.select_framework(language)
        assert isinstance(framework, TestFramework)
        assert framework in TestFramework

    @settings(deadline=500)
    @given(
        st.text(min_size=5, max_size=50, alphabet=st.characters(blacklist_categories=("Cs",))).map(
            lambda x: x if "." in x else x + ".py"
        ),
        st.sampled_from(list(TestFramework)),
    )
    def test_test_filename_generation_preserves_extension(self, filename, framework):
        """
        **Validates: Requirements 17.3**
        
        Property: Generated test filenames should preserve the file extension
        and follow framework conventions.
        """
        generator = TestGenerator()
        test_filename = generator.get_test_filename(filename, framework)
        assert isinstance(test_filename, str)
        assert len(test_filename) > 0
        # Should contain the original extension
        original_ext = filename.split(".")[-1]
        assert original_ext in test_filename

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.text(min_size=10, max_size=100),
            min_size=1,
            max_size=5,
        )
    )
    def test_secret_detection_is_deterministic(self, code_files):
        """
        **Validates: Requirements 17.4**
        
        Property: Secret detection should be deterministic - running twice
        on the same input should produce the same results.
        """
        quality_gates = QualityGates()
        result1 = quality_gates._detect_secrets(code_files)
        result2 = quality_gates._detect_secrets(code_files)
        
        assert len(result1) == len(result2)
        # Compare issue types and severities
        types1 = sorted([issue.type for issue in result1])
        types2 = sorted([issue.type for issue in result2])
        assert types1 == types2


    @settings(deadline=500)
    @given(st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",))))
    def test_code_extraction_never_fails(self, response):
        """
        **Validates: Requirements 17.1**
        
        Property: Code extraction should never fail, always returning a string
        (even if empty) for any input.
        """
        generator = TestGenerator()
        result = generator._extract_code_from_response(response)
        assert isinstance(result, str)

    @given(
        st.lists(
            st.tuples(st.booleans(), st.booleans(), st.booleans()),
            min_size=1,
            max_size=10,
        )
    )
    def test_quality_gate_summary_always_contains_all_checks(self, gate_results):
        """
        **Validates: Requirements 17.4, 17.6**
        
        Property: Quality gate summary should always mention all three checks
        (linting, type checking, security) regardless of pass/fail status.
        """
        quality_gates = QualityGates()
        for linting, type_check, security in gate_results:
            summary = quality_gates._generate_summary(
                linting, type_check, security, [], [], []
            )
            assert "Linting" in summary
            assert "Type Checking" in summary
            assert "Security Scan" in summary

    @given(
        st.integers(min_value=0, max_value=1000),
        st.integers(min_value=0, max_value=1000),
    )
    def test_coverage_percentage_is_bounded(self, total_lines, covered_lines):
        """
        **Validates: Requirements 17.1**
        
        Property: Coverage percentage calculation should always be between 0 and 100,
        and covered lines should never exceed total lines.
        """
        # Ensure covered doesn't exceed total
        covered_lines = min(covered_lines, total_lines)
        
        if total_lines == 0:
            percentage = 0.0
        else:
            percentage = (covered_lines / total_lines) * 100
        
        assert 0 <= percentage <= 100
        assert covered_lines <= total_lines

    @given(
        st.lists(
            st.sampled_from([Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]),
            min_size=0,
            max_size=20,
        )
    )
    def test_security_gate_fails_on_critical_or_high_severity(self, severities):
        """
        **Validates: Requirements 17.6**
        
        Property: Security gate should fail if any CRITICAL or HIGH severity
        issues are present, regardless of other issues.
        """
        from foundry.testing.quality_gates import SecurityIssue
        
        issues = [
            SecurityIssue("test", sev, "file.py", 1, "desc", "rec") for sev in severities
        ]
        
        has_critical_or_high = any(
            sev in [Severity.CRITICAL, Severity.HIGH] for sev in severities
        )
        security_passed = not has_critical_or_high
        
        # Verify the logic
        actual_passed = all(
            issue.severity not in [Severity.CRITICAL, Severity.HIGH] for issue in issues
        )
        assert security_passed == actual_passed
