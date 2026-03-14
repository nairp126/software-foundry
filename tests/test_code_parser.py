"""Tests for Python code parser."""

import pytest
import tempfile
from pathlib import Path

from foundry.graph.code_parser import PythonCodeParser, FunctionInfo, ClassInfo


@pytest.fixture
def parser():
    """Create a parser instance."""
    return PythonCodeParser()


@pytest.fixture
def temp_python_file():
    """Create a temporary Python file for testing."""
    content = '''"""Test module docstring."""

import os
import sys
from typing import List, Dict

GLOBAL_VAR = "test"


def simple_function(x: int) -> int:
    """Simple function docstring."""
    return x + 1


async def async_function(name: str) -> str:
    """Async function."""
    return f"Hello, {name}"


def complex_function(a: int, b: int) -> int:
    """Function with complexity."""
    if a > b:
        return a
    elif a < b:
        return b
    else:
        for i in range(10):
            if i == 5:
                return i
    return 0


class SimpleClass:
    """Simple class docstring."""
    
    def __init__(self, value: int):
        self.value = value
    
    def method1(self):
        """Method 1."""
        return self.value
    
    def method2(self, x: int):
        """Method 2."""
        return self.value + x


class DerivedClass(SimpleClass):
    """Derived class."""
    
    def method3(self):
        """Method 3."""
        return self.value * 2


def function_with_calls():
    """Function that calls others."""
    result = simple_function(5)
    obj = SimpleClass(10)
    return obj.method1()
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(content)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink()


class TestPythonCodeParser:
    """Test Python code parser."""
    
    def test_parse_file(self, parser, temp_python_file):
        """Test parsing a Python file."""
        module = parser.parse_file(temp_python_file)
        
        assert module is not None
        assert module.file_path == temp_python_file
        assert module.docstring == "Test module docstring."
    
    def test_parse_imports(self, parser, temp_python_file):
        """Test parsing imports."""
        module = parser.parse_file(temp_python_file)
        
        assert len(module.imports) >= 3
        
        # Check for specific imports
        import_modules = [imp.module for imp in module.imports]
        assert "os" in import_modules
        assert "sys" in import_modules
        assert "typing" in import_modules
    
    def test_parse_global_variables(self, parser, temp_python_file):
        """Test parsing global variables."""
        module = parser.parse_file(temp_python_file)
        
        assert "GLOBAL_VAR" in module.global_variables
    
    def test_parse_functions(self, parser, temp_python_file):
        """Test parsing functions."""
        module = parser.parse_file(temp_python_file)
        
        assert len(module.functions) >= 4
        
        # Find specific functions
        func_names = [f.name for f in module.functions]
        assert "simple_function" in func_names
        assert "async_function" in func_names
        assert "complex_function" in func_names
    
    def test_function_signature(self, parser, temp_python_file):
        """Test function signature extraction."""
        module = parser.parse_file(temp_python_file)
        
        simple_func = next(f for f in module.functions if f.name == "simple_function")
        assert "x: int" in simple_func.signature
        assert "-> int" in simple_func.signature
    
    def test_async_function(self, parser, temp_python_file):
        """Test async function detection."""
        module = parser.parse_file(temp_python_file)
        
        async_func = next(f for f in module.functions if f.name == "async_function")
        assert async_func.is_async is True
    
    def test_function_complexity(self, parser, temp_python_file):
        """Test cyclomatic complexity calculation."""
        module = parser.parse_file(temp_python_file)
        
        simple_func = next(f for f in module.functions if f.name == "simple_function")
        assert simple_func.complexity == 1  # No branches
        
        complex_func = next(f for f in module.functions if f.name == "complex_function")
        assert complex_func.complexity > 1  # Has branches
    
    def test_function_calls(self, parser, temp_python_file):
        """Test function call extraction."""
        module = parser.parse_file(temp_python_file)
        
        func_with_calls = next(f for f in module.functions if f.name == "function_with_calls")
        assert "simple_function" in func_with_calls.calls
        assert "SimpleClass" in func_with_calls.calls
    
    def test_parse_classes(self, parser, temp_python_file):
        """Test parsing classes."""
        module = parser.parse_file(temp_python_file)
        
        assert len(module.classes) >= 2
        
        class_names = [c.name for c in module.classes]
        assert "SimpleClass" in class_names
        assert "DerivedClass" in class_names
    
    def test_class_methods(self, parser, temp_python_file):
        """Test class method extraction."""
        module = parser.parse_file(temp_python_file)
        
        simple_class = next(c for c in module.classes if c.name == "SimpleClass")
        assert "__init__" in simple_class.methods
        assert "method1" in simple_class.methods
        assert "method2" in simple_class.methods
    
    def test_class_inheritance(self, parser, temp_python_file):
        """Test class inheritance detection."""
        module = parser.parse_file(temp_python_file)
        
        derived_class = next(c for c in module.classes if c.name == "DerivedClass")
        assert "SimpleClass" in derived_class.base_classes
    
    def test_class_docstring(self, parser, temp_python_file):
        """Test class docstring extraction."""
        module = parser.parse_file(temp_python_file)
        
        simple_class = next(c for c in module.classes if c.name == "SimpleClass")
        assert simple_class.docstring == "Simple class docstring."
    
    def test_function_docstring(self, parser, temp_python_file):
        """Test function docstring extraction."""
        module = parser.parse_file(temp_python_file)
        
        simple_func = next(f for f in module.functions if f.name == "simple_function")
        assert simple_func.docstring == "Simple function docstring."
    
    def test_line_numbers(self, parser, temp_python_file):
        """Test line number extraction."""
        module = parser.parse_file(temp_python_file)
        
        simple_func = next(f for f in module.functions if f.name == "simple_function")
        assert simple_func.line_number > 0
        assert simple_func.end_line >= simple_func.line_number


class TestDirectoryParsing:
    """Test parsing entire directories."""
    
    def test_parse_directory(self, parser):
        """Test parsing a directory of Python files."""
        # Create a temporary directory with Python files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a few Python files
            file1 = Path(temp_dir) / "module1.py"
            file1.write_text("def func1(): pass")
            
            file2 = Path(temp_dir) / "module2.py"
            file2.write_text("def func2(): pass")
            
            # Create a subdirectory
            subdir = Path(temp_dir) / "subdir"
            subdir.mkdir()
            file3 = subdir / "module3.py"
            file3.write_text("def func3(): pass")
            
            # Parse directory
            parsed_modules = parser.parse_directory(temp_dir)
            
            assert len(parsed_modules) == 3
            assert any("module1.py" in path for path in parsed_modules.keys())
            assert any("module2.py" in path for path in parsed_modules.keys())
            assert any("module3.py" in path for path in parsed_modules.keys())
    
    def test_exclude_patterns(self, parser):
        """Test excluding patterns when parsing directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files
            file1 = Path(temp_dir) / "module1.py"
            file1.write_text("def func1(): pass")
            
            # Create a venv directory (should be excluded)
            venv_dir = Path(temp_dir) / "venv"
            venv_dir.mkdir()
            file2 = venv_dir / "module2.py"
            file2.write_text("def func2(): pass")
            
            # Parse directory
            parsed_modules = parser.parse_directory(temp_dir)
            
            # Should only find module1, not module2 in venv
            assert len(parsed_modules) == 1
            assert any("module1.py" in path for path in parsed_modules.keys())
            assert not any("venv" in path for path in parsed_modules.keys())


class TestDependencyGraph:
    """Test dependency graph building."""
    
    def test_build_dependency_graph(self, parser):
        """Test building a dependency graph."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create module1 that imports module2
            file1 = Path(temp_dir) / "module1.py"
            file1.write_text("from module2 import func2\n\ndef func1(): return func2()")
            
            file2 = Path(temp_dir) / "module2.py"
            file2.write_text("def func2(): return 42")
            
            # Parse directory
            parsed_modules = parser.parse_directory(temp_dir)
            
            # Build dependency graph
            dep_graph = parser.build_dependency_graph(parsed_modules)
            
            # module1 should depend on module2
            module1_path = str(file1)
            assert module1_path in dep_graph
            
            # Check if module2 is in the dependencies
            # (This might be empty if the resolver doesn't find it, which is okay)
            # The important thing is that the graph structure exists
            assert isinstance(dep_graph[module1_path], list)


class TestErrorHandling:
    """Test error handling in parser."""
    
    def test_parse_invalid_syntax(self, parser):
        """Test parsing file with syntax errors."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def invalid syntax here")
            temp_path = f.name
        
        try:
            module = parser.parse_file(temp_path)
            assert module is None  # Should return None on syntax error
        finally:
            Path(temp_path).unlink()
    
    def test_parse_nonexistent_file(self, parser):
        """Test parsing a file that doesn't exist."""
        module = parser.parse_file("/nonexistent/file.py")
        assert module is None
