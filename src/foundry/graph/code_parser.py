"""Python code parser using AST for extracting code structure."""

import ast
import logging
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass, field
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """Information about a function."""
    name: str
    signature: str
    line_number: int
    end_line: int
    complexity: int
    is_async: bool
    decorators: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class ClassInfo:
    """Information about a class."""
    name: str
    line_number: int
    end_line: int
    methods: List[str] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class ImportInfo:
    """Information about an import."""
    module: str
    names: List[str] = field(default_factory=list)
    alias: Optional[str] = None
    is_from_import: bool = False


@dataclass
class ParsedModule:
    """Parsed module information."""
    file_path: str
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    global_variables: List[str] = field(default_factory=list)
    docstring: Optional[str] = None


class ComplexityVisitor(ast.NodeVisitor):
    """Calculate cyclomatic complexity of a function."""
    
    def __init__(self):
        self.complexity = 1  # Base complexity
    
    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)
    
    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)
    
    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)
    
    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)
    
    def visit_With(self, node):
        self.complexity += 1
        self.generic_visit(node)
    
    def visit_BoolOp(self, node):
        self.complexity += len(node.values) - 1
        self.generic_visit(node)


class CallVisitor(ast.NodeVisitor):
    """Extract function calls from a function body."""
    
    def __init__(self):
        self.calls: Set[str] = set()
    
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            # Handle method calls like obj.method()
            if isinstance(node.func.value, ast.Name):
                self.calls.add(f"{node.func.value.id}.{node.func.attr}")
            else:
                self.calls.add(node.func.attr)
        self.generic_visit(node)


class PythonCodeParser:
    """Parser for Python code using AST."""
    
    def __init__(self):
        self.logger = logger
    
    def parse_file(self, file_path: str) -> Optional[ParsedModule]:
        """Parse a Python file and extract structure."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source, filename=file_path)
            return self._parse_tree(tree, file_path)
        
        except SyntaxError as e:
            self.logger.error(f"Syntax error in {file_path}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing {file_path}: {e}")
            return None
    
    def _parse_tree(self, tree: ast.AST, file_path: str) -> ParsedModule:
        """Parse an AST tree."""
        module = ParsedModule(file_path=file_path)
        
        # Get module docstring
        module.docstring = ast.get_docstring(tree)
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                func_info = self._parse_function(node)
                module.functions.append(func_info)
            
            elif isinstance(node, ast.ClassDef):
                class_info = self._parse_class(node)
                module.classes.append(class_info)
            
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    import_info = ImportInfo(
                        module=alias.name,
                        alias=alias.asname,
                        is_from_import=False
                    )
                    module.imports.append(import_info)
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    import_info = ImportInfo(
                        module=node.module,
                        names=[alias.name for alias in node.names],
                        is_from_import=True
                    )
                    module.imports.append(import_info)
            
            elif isinstance(node, ast.Assign):
                # Extract global variables
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        module.global_variables.append(target.id)
        
        return module
    
    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionInfo:
        """Parse a function definition."""
        # Calculate complexity
        complexity_visitor = ComplexityVisitor()
        complexity_visitor.visit(node)
        
        # Extract function calls
        call_visitor = CallVisitor()
        call_visitor.visit(node)
        
        # Build signature
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)
        
        # Handle *args and **kwargs
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        
        signature = f"{node.name}({', '.join(args)})"
        
        # Add return type if present
        if node.returns:
            signature += f" -> {ast.unparse(node.returns)}"
        
        # Extract decorators
        decorators = [ast.unparse(dec) for dec in node.decorator_list]
        
        return FunctionInfo(
            name=node.name,
            signature=signature,
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            complexity=complexity_visitor.complexity,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decorators,
            calls=list(call_visitor.calls),
            docstring=ast.get_docstring(node)
        )
    
    def _parse_class(self, node: ast.ClassDef) -> ClassInfo:
        """Parse a class definition."""
        # Extract methods
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
        
        # Extract base classes
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(ast.unparse(base))
        
        # Extract decorators
        decorators = [ast.unparse(dec) for dec in node.decorator_list]
        
        return ClassInfo(
            name=node.name,
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            methods=methods,
            base_classes=base_classes,
            decorators=decorators,
            docstring=ast.get_docstring(node)
        )
    
    def parse_directory(
        self,
        directory: str,
        exclude_patterns: Optional[List[str]] = None
    ) -> Dict[str, ParsedModule]:
        """Parse all Python files in a directory."""
        exclude_patterns = exclude_patterns or [
            "venv", "env", ".venv", "__pycache__", ".git", "node_modules",
            "build", "dist", ".pytest_cache", ".mypy_cache"
        ]
        
        parsed_modules = {}
        directory_path = Path(directory)
        
        for py_file in directory_path.rglob("*.py"):
            # Skip excluded directories
            if any(pattern in str(py_file) for pattern in exclude_patterns):
                continue
            
            parsed = self.parse_file(str(py_file))
            if parsed:
                parsed_modules[str(py_file)] = parsed
        
        return parsed_modules
    
    def build_dependency_graph(
        self,
        parsed_modules: Dict[str, ParsedModule]
    ) -> Dict[str, List[str]]:
        """Build a dependency graph from parsed modules."""
        dependencies = {}
        
        # Create a mapping of module names to file paths
        module_map = {}
        for file_path, module in parsed_modules.items():
            # Extract module name from file path
            module_name = Path(file_path).stem
            module_map[module_name] = file_path
        
        # Build dependencies based on imports
        for file_path, module in parsed_modules.items():
            deps = []
            for import_info in module.imports:
                # Try to resolve import to a file in the project
                module_parts = import_info.module.split('.')
                for i in range(len(module_parts), 0, -1):
                    potential_module = '.'.join(module_parts[:i])
                    if potential_module in module_map:
                        target_file = module_map[potential_module]
                        if target_file != file_path:
                            deps.append(target_file)
                        break
            
            dependencies[file_path] = deps
        
        return dependencies


# Global parser instance
python_parser = PythonCodeParser()
