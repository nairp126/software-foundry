"""Regex-based JavaScript/TypeScript parser for Knowledge Graph ingestion."""

import re
import logging
from typing import Optional, List
from pathlib import Path
from dataclasses import dataclass, field

from foundry.graph.code_parser import ParsedModule, FunctionInfo, ClassInfo, ImportInfo

logger = logging.getLogger(__name__)

# Regex patterns for JS/TS constructs
_NAMED_FUNC = re.compile(
    r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(', re.MULTILINE
)
_ARROW_FUNC = re.compile(
    r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(.*?\)\s*=>', re.MULTILINE
)
_CLASS_DECL = re.compile(
    r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)', re.MULTILINE
)
_ES_IMPORT = re.compile(
    r"import\s+(?:.*?\s+from\s+)?['\"]([^'\"]+)['\"]", re.MULTILINE
)
_REQUIRE = re.compile(
    r"(?:const|let|var)\s+\{?(\w+)\}?\s*=\s*require\(['\"]([^'\"]+)['\"]\)", re.MULTILINE
)


class JSParser:
    """Regex-based parser for .js and .ts files."""

    def parse_file(self, file_path: str) -> Optional[ParsedModule]:
        """Parse a JS/TS file and return a ParsedModule, or None on error."""
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                source = fh.read()
            return self.parse_source(source, file_path)
        except Exception as e:
            logger.error(f"JSParser.parse_file failed for {file_path}: {e}")
            return None

    def parse_source(self, source: str, file_path: str) -> ParsedModule:
        """Parse JS/TS source text and return a ParsedModule."""
        module = ParsedModule(file_path=file_path)

        # Named functions
        for m in _NAMED_FUNC.finditer(source):
            module.functions.append(
                FunctionInfo(
                    name=m.group(1),
                    signature=f"{m.group(1)}(...)",
                    line_number=source[: m.start()].count("\n") + 1,
                    end_line=source[: m.start()].count("\n") + 1,
                    complexity=1,
                    is_async="async" in source[max(0, m.start() - 10): m.start()],
                )
            )

        # Arrow functions assigned to const/let/var
        for m in _ARROW_FUNC.finditer(source):
            module.functions.append(
                FunctionInfo(
                    name=m.group(1),
                    signature=f"{m.group(1)}(...)",
                    line_number=source[: m.start()].count("\n") + 1,
                    end_line=source[: m.start()].count("\n") + 1,
                    complexity=1,
                    is_async="async" in m.group(0),
                )
            )

        # Class declarations
        for m in _CLASS_DECL.finditer(source):
            module.classes.append(
                ClassInfo(
                    name=m.group(1),
                    line_number=source[: m.start()].count("\n") + 1,
                    end_line=source[: m.start()].count("\n") + 1,
                )
            )

        # ES module imports
        for m in _ES_IMPORT.finditer(source):
            module.imports.append(
                ImportInfo(module=m.group(1), is_from_import=True)
            )

        # CommonJS require()
        for m in _REQUIRE.finditer(source):
            module.imports.append(
                ImportInfo(module=m.group(2), names=[m.group(1)], is_from_import=False)
            )

        return module


# Singleton
js_parser = JSParser()
