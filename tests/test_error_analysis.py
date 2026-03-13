"""Unit tests for error analysis and fix generation."""

import pytest
from foundry.sandbox.error_analysis import (
    ErrorAnalyzer,
    FixGenerator,
    ErrorType,
    ErrorSeverity,
    ErrorAnalysis,
    CodeFix,
)


class TestErrorAnalyzer:
    """Test suite for ErrorAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an error analyzer for testing."""
        return ErrorAnalyzer()
    
    def test_analyze_syntax_error(self, analyzer):
        """Test analyzing a syntax error."""
        stderr = """
        File "test.py", line 5
            if x = 5:
               ^
        SyntaxError: invalid syntax
        """
        
        analysis = analyzer.analyze_error(
            error_message="SyntaxError: invalid syntax",
            stderr=stderr,
            exit_code=1,
            code_content="if x = 5:\n    print(x)"
        )
        
        assert analysis.error_type == ErrorType.SYNTAX_ERROR
        assert analysis.severity == ErrorSeverity.HIGH
        assert len(analysis.stack_trace) > 0
        assert len(analysis.suggested_fixes) > 0
    
    def test_analyze_name_error(self, analyzer):
        """Test analyzing a name error."""
        stderr = """
        Traceback (most recent call last):
          File "test.py", line 3, in <module>
            print(undefined_var)
        NameError: name 'undefined_var' is not defined
        """
        
        analysis = analyzer.analyze_error(
            error_message="NameError: name 'undefined_var' is not defined",
            stderr=stderr,
            exit_code=1,
            code_content="print(undefined_var)"
        )
        
        assert analysis.error_type == ErrorType.NAME_ERROR
        assert analysis.severity == ErrorSeverity.HIGH
        assert "undefined_var" in analysis.error_message
        assert len(analysis.suggested_fixes) > 0
    
    def test_analyze_import_error(self, analyzer):
        """Test analyzing an import error."""
        stderr = """
        Traceback (most recent call last):
          File "test.py", line 1, in <module>
            import nonexistent_module
        ModuleNotFoundError: No module named 'nonexistent_module'
        """
        
        analysis = analyzer.analyze_error(
            error_message="ModuleNotFoundError: No module named 'nonexistent_module'",
            stderr=stderr,
            exit_code=1,
            code_content="import nonexistent_module"
        )
        
        assert analysis.error_type == ErrorType.IMPORT_ERROR
        assert analysis.severity == ErrorSeverity.HIGH
        assert any("install" in fix.lower() for fix in analysis.suggested_fixes)
    
    def test_analyze_type_error(self, analyzer):
        """Test analyzing a type error."""
        stderr = """
        Traceback (most recent call last):
          File "test.py", line 2, in <module>
            result = "string" + 5
        TypeError: can only concatenate str (not "int") to str
        """
        
        analysis = analyzer.analyze_error(
            error_message="TypeError: can only concatenate str (not 'int') to str",
            stderr=stderr,
            exit_code=1,
            code_content='result = "string" + 5'
        )
        
        assert analysis.error_type == ErrorType.TYPE_ERROR
        assert analysis.severity == ErrorSeverity.MEDIUM
    
    def test_analyze_timeout_error(self, analyzer):
        """Test analyzing a timeout error."""
        stderr = "Execution timeout after 300 seconds"
        
        analysis = analyzer.analyze_error(
            error_message="Execution timeout",
            stderr=stderr,
            exit_code=-1,
            code_content="while True: pass"
        )
        
        assert analysis.error_type == ErrorType.TIMEOUT_ERROR
        assert analysis.severity == ErrorSeverity.HIGH
        assert any("optimize" in fix.lower() for fix in analysis.suggested_fixes)
    
    def test_analyze_memory_error(self, analyzer):
        """Test analyzing a memory error."""
        stderr = """
        Traceback (most recent call last):
          File "test.py", line 2, in <module>
            big_list = [0] * (10**10)
        MemoryError
        """
        
        analysis = analyzer.analyze_error(
            error_message="MemoryError",
            stderr=stderr,
            exit_code=1,
            code_content="big_list = [0] * (10**10)"
        )
        
        assert analysis.error_type == ErrorType.MEMORY_ERROR
        assert analysis.severity == ErrorSeverity.CRITICAL
        assert any("chunk" in fix.lower() for fix in analysis.suggested_fixes)
    
    def test_extract_line_numbers(self, analyzer):
        """Test extracting line numbers from error messages."""
        stderr = """
        File "test.py", line 5
        File "module.py", line 42
        """
        
        line_numbers = analyzer._extract_line_numbers(stderr)
        
        assert 5 in line_numbers
        assert 42 in line_numbers
    
    def test_extract_stack_trace(self, analyzer):
        """Test extracting stack trace from stderr."""
        stderr = """
        Traceback (most recent call last):
          File "test.py", line 3, in <module>
            result = func()
          File "test.py", line 1, in func
            return undefined
        NameError: name 'undefined' is not defined
        """
        
        stack_trace = analyzer._extract_stack_trace(stderr)
        
        assert len(stack_trace) > 0
        assert any("Traceback" in line for line in stack_trace)


class TestFixGenerator:
    """Test suite for FixGenerator."""
    
    @pytest.fixture
    def generator(self):
        """Create a fix generator for testing."""
        return FixGenerator()
    
    def test_generate_import_error_fix(self, generator):
        """Test generating fix for import error."""
        analysis = ErrorAnalysis(
            error_type=ErrorType.IMPORT_ERROR,
            severity=ErrorSeverity.HIGH,
            error_message="ModuleNotFoundError: No module named 'requests'",
            stack_trace=[],
            root_cause="Module not installed",
            affected_lines=[1],
            suggested_fixes=["Install the 'requests' package"]
        )
        
        fixes = generator.generate_fixes(
            analysis=analysis,
            code_content="import requests",
            filename="test.py"
        )
        
        assert len(fixes) > 0
        assert fixes[0].fix_type == "insert"
        assert "import" in fixes[0].fixed_code
    
    def test_generate_name_error_fix(self, generator):
        """Test generating fix for name error."""
        analysis = ErrorAnalysis(
            error_type=ErrorType.NAME_ERROR,
            severity=ErrorSeverity.HIGH,
            error_message="NameError: name 'x' is not defined",
            stack_trace=[],
            root_cause="Variable not defined",
            affected_lines=[5],
            suggested_fixes=["Define 'x' before using it"]
        )
        
        fixes = generator.generate_fixes(
            analysis=analysis,
            code_content="print(x)",
            filename="test.py"
        )
        
        assert len(fixes) > 0
        assert fixes[0].fix_type == "insert"
        assert "x" in fixes[0].fixed_code
    
    def test_generate_syntax_error_fix(self, generator):
        """Test that syntax errors return empty list (requires LLM)."""
        analysis = ErrorAnalysis(
            error_type=ErrorType.SYNTAX_ERROR,
            severity=ErrorSeverity.HIGH,
            error_message="SyntaxError: invalid syntax",
            stack_trace=[],
            root_cause="Syntax error",
            affected_lines=[3],
            suggested_fixes=["Fix syntax"]
        )
        
        fixes = generator.generate_fixes(
            analysis=analysis,
            code_content="if x = 5:",
            filename="test.py"
        )
        
        # Syntax errors should return empty list to trigger LLM
        assert len(fixes) == 0
    
    def test_code_fix_creation(self):
        """Test creating a CodeFix object."""
        fix = CodeFix(
            fix_type="replace",
            target_file="test.py",
            line_number=5,
            original_code="x = undefined",
            fixed_code="x = None",
            explanation="Initialize variable"
        )
        
        assert fix.fix_type == "replace"
        assert fix.target_file == "test.py"
        assert fix.line_number == 5
        assert fix.fixed_code == "x = None"


class TestErrorAnalysis:
    """Test suite for ErrorAnalysis dataclass."""
    
    def test_error_analysis_creation(self):
        """Test creating an ErrorAnalysis object."""
        analysis = ErrorAnalysis(
            error_type=ErrorType.NAME_ERROR,
            severity=ErrorSeverity.HIGH,
            error_message="NameError: name 'x' is not defined",
            stack_trace=["line 1", "line 2"],
            root_cause="Variable not defined",
            affected_lines=[5],
            suggested_fixes=["Define x before use"]
        )
        
        assert analysis.error_type == ErrorType.NAME_ERROR
        assert analysis.severity == ErrorSeverity.HIGH
        assert len(analysis.stack_trace) == 2
        assert len(analysis.affected_lines) == 1
        assert len(analysis.suggested_fixes) == 1
    
    def test_error_analysis_with_context(self):
        """Test ErrorAnalysis with additional context."""
        analysis = ErrorAnalysis(
            error_type=ErrorType.RUNTIME_ERROR,
            severity=ErrorSeverity.MEDIUM,
            error_message="Runtime error",
            stack_trace=[],
            root_cause="Unknown",
            affected_lines=[],
            suggested_fixes=[],
            context={"exit_code": 1, "execution_time": 0.5}
        )
        
        assert "exit_code" in analysis.context
        assert analysis.context["exit_code"] == 1
