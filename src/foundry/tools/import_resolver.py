import ast
import os
import logging
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

class ImportResolver:
    """
    Static analysis tool to resolve and verify imports in a generated repository.
    Catches ModuleNotFoundError issues before sandbox execution.
    """
    
    def __init__(self, repo_content: Dict[str, str]):
        self.repo_content = repo_content
        self.all_files = set(repo_content.keys())
        
    def resolve_all(self) -> Dict[str, Any]:
        """Runs import resolution on the entire repository."""
        report = {
            "missing_internal_imports": [],
            "potential_external_dependencies": set(),
            "syntax_errors": []
        }
        
        for file_path, content in self.repo_content.items():
            if not file_path.endswith('.py'):
                continue
                
            try:
                tree = ast.parse(content)
                imports = self._extract_imports(tree)
                
                for imp in imports:
                    if self._is_internal(imp, file_path):
                        if not self._verify_internal_import(imp, file_path):
                            report["missing_internal_imports"].append({
                                "file": file_path,
                                "import": imp
                            })
                    else:
                        # Likely an external dependency
                        # We only track the top-level package name
                        package = imp.split('.')[0]
                        if package not in ['os', 'sys', 'json', 're', 'asyncio', 'logging', 'datetime', 'typing', 'math', 'collections', 'pathlib', 'abc', 'functools']:
                             report["potential_external_dependencies"].add(package)
                             
            except SyntaxError as e:
                report["syntax_errors"].append({
                    "file": file_path,
                    "line": e.lineno,
                    "error": str(e)
                })
        
        report["potential_external_dependencies"] = list(report["potential_external_dependencies"])
        return report

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(name.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    def _is_internal(self, import_name: str, current_file: str) -> bool:
        """Determines if an import refers to another file in the project."""
        # Simple heuristic: if the first part of the import matches a file/folder in the repo
        parts = import_name.split('.')
        first_part = parts[0]
        
        # Check direct files
        if f"{first_part}.py" in self.all_files:
            return True
        if f"src/{first_part}.py" in self.all_files:
            return True
            
        # Check subdirectories
        for f in self.all_files:
            if f.startswith(f"{first_part}/") or f.startswith(f"src/{first_part}/"):
                return True
                
        return False

    def _verify_internal_import(self, import_name: str, current_file: str) -> bool:
        """Verifies that an internal import actually exists in the project."""
        # Convert import name (dot notation) to path
        rel_path = import_name.replace('.', '/')
        
        # Candidate paths
        candidates = [
            f"{rel_path}.py",
            f"{rel_path}/__init__.py",
            f"src/{rel_path}.py",
            f"src/{rel_path}/__init__.py"
        ]
        
        # Also check relative to current file if it's in a subfolder
        current_dir = os.path.dirname(current_file)
        if current_dir:
             candidates.append(os.path.join(current_dir, f"{rel_path}.py"))
             candidates.append(os.path.join(current_dir, f"{rel_path}/__init__.py"))

        for cand in candidates:
            # Normalize path
            norm_cand = cand.replace('\\', '/').strip('/')
            if norm_cand in self.all_files:
                return True
                
        return False

    @staticmethod
    def discover_entry_point(repo_content: Dict[str, str]) -> str:
        """Heuristically finds the most likely entry point of the project."""
        # 1. Look for main.py in src/ or root
        entry_candidates = ["src/main.py", "main.py", "app.py", "src/app.py"]
        for cand in entry_candidates:
            if cand in repo_content:
                return cand
                
        # 2. Look for any file containing the __main__ block
        for file_path, content in repo_content.items():
            if '__name__ == "__main__"' in content or "__name__ == '__main__'" in content:
                return file_path
                
        # 3. Fallback to any python file in src/ (pick the shortest one)
        src_files = [f for f in repo_content.keys() if f.startswith('src/') and f.endswith('.py')]
        if src_files:
            return min(src_files, key=len)
            
        # 4. Global fallback
        py_files = [f for f in repo_content.keys() if f.endswith('.py')]
        if py_files:
            return min(py_files, key=len)
            
        return "main.py"
