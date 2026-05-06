"""Error analysis and correction system for the Reflexion Engine."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """Types of errors that can be detected."""
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    TYPE_ERROR = "type_error"
    IMPORT_ERROR = "import_error"
    NAME_ERROR = "name_error"
    ATTRIBUTE_ERROR = "attribute_error"
    INDEX_ERROR = "index_error"
    KEY_ERROR = "key_error"
    VALUE_ERROR = "value_error"
    TIMEOUT_ERROR = "timeout_error"
    MEMORY_ERROR = "memory_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorSeverity(str, Enum):
    """Severity levels for errors."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ErrorPattern:
    """Pattern for matching and classifying errors."""
    pattern: str
    error_type: ErrorType
    severity: ErrorSeverity
    description: str
    fix_strategy: str


@dataclass
class ErrorAnalysis:
    """Analysis of execution errors."""
    error_type: ErrorType
    severity: ErrorSeverity
    error_message: str
    stack_trace: List[str]
    root_cause: str
    affected_lines: List[int]
    suggested_fixes: List[str]
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeFix:
    """Represents a code fix to be applied."""
    fix_type: str  # replace, insert, delete
    target_file: str
    line_number: Optional[int]
    original_code: Optional[str]
    fixed_code: str
    explanation: str


class ErrorAnalyzer:
    """
    Analyzes execution errors and generates fix suggestions.
    
    Implements root cause analysis for common error patterns and provides
    actionable fix strategies.
    """
    
    # Common error patterns with fix strategies
    ERROR_PATTERNS = [
        ErrorPattern(
            pattern=r"SyntaxError: (.+)",
            error_type=ErrorType.SYNTAX_ERROR,
            severity=ErrorSeverity.HIGH,
            description="Syntax error in code",
            fix_strategy="Review syntax at the indicated line and fix structural issues"
        ),
        ErrorPattern(
            pattern=r"NameError: name '(\w+)' is not defined",
            error_type=ErrorType.NAME_ERROR,
            severity=ErrorSeverity.HIGH,
            description="Variable or function not defined",
            fix_strategy="Define the variable or import the required module"
        ),
        ErrorPattern(
            pattern=r"ImportError: (.+)|ModuleNotFoundError: (.+)",
            error_type=ErrorType.IMPORT_ERROR,
            severity=ErrorSeverity.HIGH,
            description="Module import failed",
            fix_strategy="Install missing dependency or fix import path"
        ),
        ErrorPattern(
            pattern=r"TypeError: (.+)",
            error_type=ErrorType.TYPE_ERROR,
            severity=ErrorSeverity.MEDIUM,
            description="Type mismatch or invalid operation",
            fix_strategy="Check types and ensure operations are valid for the data types"
        ),
        ErrorPattern(
            pattern=r"AttributeError: (.+) has no attribute '(\w+)'",
            error_type=ErrorType.ATTRIBUTE_ERROR,
            severity=ErrorSeverity.MEDIUM,
            description="Attribute does not exist on object",
            fix_strategy="Check object type and available attributes"
        ),
        ErrorPattern(
            pattern=r"IndexError: (.+)",
            error_type=ErrorType.INDEX_ERROR,
            severity=ErrorSeverity.MEDIUM,
            description="Index out of range",
            fix_strategy="Check array/list bounds before accessing"
        ),
        ErrorPattern(
            pattern=r"KeyError: (.+)",
            error_type=ErrorType.KEY_ERROR,
            severity=ErrorSeverity.MEDIUM,
            description="Dictionary key not found",
            fix_strategy="Check if key exists before accessing or use .get() method"
        ),
        ErrorPattern(
            pattern=r"ValueError: (.+)",
            error_type=ErrorType.VALUE_ERROR,
            severity=ErrorSeverity.MEDIUM,
            description="Invalid value for operation",
            fix_strategy="Validate input values before processing"
        ),
        ErrorPattern(
            pattern=r"timeout|TimeoutError",
            error_type=ErrorType.TIMEOUT_ERROR,
            severity=ErrorSeverity.HIGH,
            description="Execution timeout",
            fix_strategy="Optimize code performance or increase timeout limit"
        ),
        ErrorPattern(
            pattern=r"MemoryError|OutOfMemoryError",
            error_type=ErrorType.MEMORY_ERROR,
            severity=ErrorSeverity.CRITICAL,
            description="Out of memory",
            fix_strategy="Reduce memory usage or process data in chunks"
        ),
    ]
    
    def analyze_error(
        self,
        error_message: str,
        stderr: str,
        exit_code: int,
        code_content: str
    ) -> ErrorAnalysis:
        """
        Analyze an error and provide root cause analysis.
        
        Args:
            error_message: Primary error message
            stderr: Full stderr output
            exit_code: Process exit code
            code_content: The code that was executed
            
        Returns:
            ErrorAnalysis with detailed analysis
        """
        # Extract stack trace
        stack_trace = self._extract_stack_trace(stderr)
        
        # Classify error type
        error_type, severity, matched_pattern = self._classify_error(stderr)
        
        # Extract affected line numbers
        affected_lines = self._extract_line_numbers(stderr)
        
        # Determine root cause
        root_cause = self._determine_root_cause(
            error_type, error_message, stderr, code_content
        )
        
        # Generate fix suggestions
        suggested_fixes = self._generate_fix_suggestions(
            error_type, matched_pattern, error_message, code_content
        )
        
        return ErrorAnalysis(
            error_type=error_type,
            severity=severity,
            error_message=error_message,
            stack_trace=stack_trace,
            root_cause=root_cause,
            affected_lines=affected_lines,
            suggested_fixes=suggested_fixes,
            context={
                "exit_code": exit_code,
                "stderr_length": len(stderr),
                "code_length": len(code_content),
            }
        )
    
    def _extract_stack_trace(self, stderr: str) -> List[str]:
        """Extract stack trace lines from stderr."""
        lines = stderr.split('\n')
        stack_trace = []
        
        in_traceback = False
        for line in lines:
            if 'Traceback' in line or 'Error' in line or 'Exception' in line:
                in_traceback = True
            if in_traceback and line.strip():
                stack_trace.append(line.strip())
        
        return stack_trace
    
    def _classify_error(
        self, stderr: str
    ) -> tuple[ErrorType, ErrorSeverity, Optional[ErrorPattern]]:
        """Classify error type and severity."""
        for pattern in self.ERROR_PATTERNS:
            if re.search(pattern.pattern, stderr, re.IGNORECASE):
                return pattern.error_type, pattern.severity, pattern
        
        return ErrorType.UNKNOWN_ERROR, ErrorSeverity.MEDIUM, None
    
    def _extract_line_numbers(self, stderr: str) -> List[int]:
        """Extract line numbers mentioned in error messages."""
        line_numbers = []
        
        # Match patterns like "line 42" or "line 42,"
        matches = re.findall(r'line (\d+)', stderr, re.IGNORECASE)
        for match in matches:
            line_numbers.append(int(match))
        
        return sorted(set(line_numbers))
    
    def _determine_root_cause(
        self,
        error_type: ErrorType,
        error_message: str,
        stderr: str,
        code_content: str
    ) -> str:
        """Determine the root cause of the error."""
        root_causes = {
            ErrorType.SYNTAX_ERROR: "Code contains syntax errors that prevent parsing",
            ErrorType.NAME_ERROR: "Variable or function referenced before definition",
            ErrorType.IMPORT_ERROR: "Required module is not installed or import path is incorrect",
            ErrorType.TYPE_ERROR: "Operation performed on incompatible data types",
            ErrorType.ATTRIBUTE_ERROR: "Attempted to access non-existent attribute on object",
            ErrorType.INDEX_ERROR: "Array or list accessed with out-of-bounds index",
            ErrorType.KEY_ERROR: "Dictionary accessed with non-existent key",
            ErrorType.VALUE_ERROR: "Function received argument with invalid value",
            ErrorType.TIMEOUT_ERROR: "Code execution exceeded time limit",
            ErrorType.MEMORY_ERROR: "Code consumed more memory than available",
            ErrorType.RUNTIME_ERROR: "Runtime error during code execution",
        }
        
        base_cause = root_causes.get(error_type, "Unknown error occurred during execution")
        
        # Add specific details from error message
        if error_message:
            return f"{base_cause}: {error_message}"
        
        return base_cause
    
    def _generate_fix_suggestions(
        self,
        error_type: ErrorType,
        matched_pattern: Optional[ErrorPattern],
        error_message: str,
        code_content: str
    ) -> List[str]:
        """Generate actionable fix suggestions."""
        suggestions = []
        
        # Add pattern-based suggestion
        if matched_pattern:
            suggestions.append(matched_pattern.fix_strategy)
        
        # Add error-specific suggestions
        if error_type == ErrorType.IMPORT_ERROR:
            # Extract module name
            module_match = re.search(r"No module named '(\w+)'", error_message)
            if module_match:
                module_name = module_match.group(1)
                suggestions.append(f"Install the '{module_name}' package using pip or npm")
        
        elif error_type == ErrorType.NAME_ERROR:
            # Extract variable name
            var_match = re.search(r"name '(\w+)' is not defined", error_message)
            if var_match:
                var_name = var_match.group(1)
                suggestions.append(f"Define '{var_name}' before using it or check for typos")
        
        elif error_type == ErrorType.SYNTAX_ERROR:
            suggestions.append("Check for missing colons, parentheses, or brackets")
            suggestions.append("Verify proper indentation")
        
        elif error_type == ErrorType.TYPE_ERROR:
            suggestions.append("Add type checking or conversion before operations")
            suggestions.append("Review function signatures and argument types")
        
        elif error_type == ErrorType.TIMEOUT_ERROR:
            suggestions.append("Optimize loops and recursive functions")
            suggestions.append("Consider using more efficient algorithms")
            suggestions.append("Add early exit conditions")
        
        elif error_type == ErrorType.MEMORY_ERROR:
            suggestions.append("Process data in smaller chunks")
            suggestions.append("Use generators instead of loading all data into memory")
            suggestions.append("Clear unused variables and data structures")
        
        # Generic suggestion if no specific ones
        if not suggestions:
            suggestions.append("Review the error message and stack trace carefully")
            suggestions.append("Check the code at the indicated line numbers")
        
        return suggestions


class FixGenerator:
    """Generates code fixes based on error analysis."""
    
    def generate_fixes(
        self,
        analysis: ErrorAnalysis,
        code_content: str,
        filename: str
    ) -> List[CodeFix]:
        """
        Generate code fixes based on error analysis.
        
        Args:
            analysis: Error analysis results
            code_content: Original code content
            filename: Name of the file with errors
            
        Returns:
            List of CodeFix objects
        """
        fixes = []
        
        # Generate fixes based on error type
        if analysis.error_type == ErrorType.IMPORT_ERROR:
            fixes.extend(self._fix_import_error(analysis, code_content, filename))
        
        elif analysis.error_type == ErrorType.NAME_ERROR:
            fixes.extend(self._fix_name_error(analysis, code_content, filename))
        
        elif analysis.error_type == ErrorType.SYNTAX_ERROR:
            fixes.extend(self._fix_syntax_error(analysis, code_content, filename))
        
        elif analysis.error_type == ErrorType.TYPE_ERROR:
            fixes.extend(self._fix_type_error(analysis, code_content, filename))
        
        return fixes
    
    def _fix_import_error(
        self, analysis: ErrorAnalysis, code_content: str, filename: str
    ) -> List[CodeFix]:
        """Generate fixes for import errors."""
        fixes = []
        
        # Extract module name from error
        module_match = re.search(r"No module named '(\w+)'", analysis.error_message)
        if module_match:
            module_name = module_match.group(1)
            
            # Suggest adding import statement
            fixes.append(CodeFix(
                fix_type="insert",
                target_file=filename,
                line_number=1,
                original_code=None,
                fixed_code=f"import {module_name}",
                explanation=f"Add missing import for '{module_name}' module"
            ))
        
        return fixes
    
    def _fix_name_error(
        self, analysis: ErrorAnalysis, code_content: str, filename: str
    ) -> List[CodeFix]:
        """Generate fixes for name errors."""
        fixes = []
        
        # Extract variable name
        var_match = re.search(r"name '(\w+)' is not defined", analysis.error_message)
        if var_match:
            var_name = var_match.group(1)
            
            # Suggest defining the variable
            if analysis.affected_lines:
                line_num = analysis.affected_lines[0]
                fixes.append(CodeFix(
                    fix_type="insert",
                    target_file=filename,
                    line_number=line_num - 1,
                    original_code=None,
                    fixed_code=f"{var_name} = None  # TODO: Initialize {var_name}",
                    explanation=f"Initialize '{var_name}' before use"
                ))
        
        return fixes
    
    def _fix_syntax_error(
        self, analysis: ErrorAnalysis, code_content: str, filename: str
    ) -> List[CodeFix]:
        """Generate fixes for syntax errors."""
        # Syntax errors are complex and usually require LLM assistance
        # Return empty list to trigger LLM-based fix generation
        return []
    
    def _fix_type_error(
        self, analysis: ErrorAnalysis, code_content: str, filename: str
    ) -> List[CodeFix]:
        """Generate fixes for type errors."""
        # Type errors often require context-aware fixes
        # Return empty list to trigger LLM-based fix generation
        return []
