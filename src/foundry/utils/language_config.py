from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class LanguageConfig:
    name: str
    extensions: List[str]
    entry_point: str
    package_file: str
    test_pattern: str
    linters: List[str]
    test_framework: str
    base_image: str
    coding_standard: str
    web_frameworks: List[str]
    forbidden_patterns: List[str] = field(default_factory=list)

LANGUAGE_CONFIGS: Dict[str, LanguageConfig] = {
    "python": LanguageConfig(
        name="python",
        extensions=[".py"],
        entry_point="main.py",
        package_file="requirements.txt",
        test_pattern="test_*.py",
        linters=["pylint", "mypy", "bandit"],
        test_framework="pytest",
        base_image="python:3.11-slim",
        coding_standard="PEP 8",
        web_frameworks=["FastAPI", "Flask", "Django"],
        forbidden_patterns=[r"console\.log", r"require\(", r"import .* from"]
    ),
    "javascript": LanguageConfig(
        name="javascript",
        extensions=[".js", ".jsx"],
        entry_point="index.js",
        package_file="package.json",
        test_pattern="*.test.js",
        linters=["eslint"],
        test_framework="jest",
        base_image="node:20-alpine",
        coding_standard="Airbnb/Standard",
        web_frameworks=["Express", "React", "Next.js"],
        forbidden_patterns=[r"def ", r"import .* as "]
    ),
    "typescript": LanguageConfig(
        name="typescript",
        extensions=[".ts", ".tsx"],
        entry_point="index.ts",
        package_file="package.json",
        test_pattern="*.test.ts",
        linters=["eslint", "tsc"],
        test_framework="jest",
        base_image="node:20-alpine",
        coding_standard="Airbnb/Standard",
        web_frameworks=["Express", "React", "Next.js", "NestJS"],
        forbidden_patterns=[r"def ", r"import .* as "]
    ),
    "java": LanguageConfig(
        name="java",
        extensions=[".java"],
        entry_point="Main.java",
        package_file="pom.xml",
        test_pattern="*Test.java",
        linters=["checkstyle"],
        test_framework="JUnit",
        base_image="eclipse-temurin:21-jre-alpine",
        coding_standard="Google Java Style",
        web_frameworks=["Spring Boot", "Micronaut"],
        forbidden_patterns=[r"def ", r"function "]
    )
}

def get_language_config(language: str) -> LanguageConfig:
    """Get config for language, with python fallback."""
    lang = (language or "python").lower().strip()
    return LANGUAGE_CONFIGS.get(lang, LANGUAGE_CONFIGS["python"])
