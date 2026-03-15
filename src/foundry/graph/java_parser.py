"""Regex-based Java parser for Knowledge Graph ingestion."""

import re
import logging
from typing import Optional
from pathlib import Path

from foundry.graph.code_parser import ParsedModule, FunctionInfo, ClassInfo, ImportInfo

logger = logging.getLogger(__name__)

# Regex patterns for Java constructs
_CLASS_DECL = re.compile(
    r'(?:public\s+|protected\s+|private\s+)?(?:abstract\s+|final\s+)?class\s+(\w+)', re.MULTILINE
)
_METHOD_DECL = re.compile(
    r'(?:public|protected|private|static|final|abstract|synchronized|native|strictfp|\s)+'
    r'(?:<[^>]+>\s+)?'
    r'(?:\w+(?:\[\])*\s+)'
    r'(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{',
    re.MULTILINE,
)
_IMPORT = re.compile(r'import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;', re.MULTILINE)


class JavaParser:
    """Regex-based parser for .java files."""

    def parse_file(self, file_path: str) -> Optional[ParsedModule]:
        """Parse a Java file and return a ParsedModule, or None on error."""
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                source = fh.read()
            return self.parse_source(source, file_path)
        except Exception as e:
            logger.error(f"JavaParser.parse_file failed for {file_path}: {e}")
            return None

    def parse_source(self, source: str, file_path: str) -> ParsedModule:
        """Parse Java source text and return a ParsedModule."""
        module = ParsedModule(file_path=file_path)

        # Class declarations
        for m in _CLASS_DECL.finditer(source):
            module.classes.append(
                ClassInfo(
                    name=m.group(1),
                    line_number=source[: m.start()].count("\n") + 1,
                    end_line=source[: m.start()].count("\n") + 1,
                )
            )

        # Method signatures
        for m in _METHOD_DECL.finditer(source):
            name = m.group(1)
            # Skip common false positives (control flow keywords)
            if name in {"if", "for", "while", "switch", "catch", "try"}:
                continue
            module.functions.append(
                FunctionInfo(
                    name=name,
                    signature=f"{name}(...)",
                    line_number=source[: m.start()].count("\n") + 1,
                    end_line=source[: m.start()].count("\n") + 1,
                    complexity=1,
                    is_async=False,
                )
            )

        # Import statements
        for m in _IMPORT.finditer(source):
            module.imports.append(ImportInfo(module=m.group(1), is_from_import=True))

        return module


# Singleton
java_parser = JavaParser()
