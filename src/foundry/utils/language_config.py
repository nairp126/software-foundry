"""Single source of truth for per-language configuration settings."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

LANGUAGE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "python": {
        "name": "python",
        "extension": ".py",
        "test_framework": "pytest",
        "web_framework": "fastapi",
        "package_manager": "pip",
        "base_image": "python:3.11-slim",
        "coding_standard": "PEP 8",
    },
    "javascript": {
        "name": "javascript",
        "extension": ".js",
        "test_framework": "jest",
        "web_framework": "express",
        "package_manager": "npm",
        "base_image": "node:20-alpine",
        "coding_standard": "ESLint Standard",
    },
    "typescript": {
        "name": "typescript",
        "extension": ".ts",
        "test_framework": "vitest",
        "web_framework": "express",
        "package_manager": "npm",
        "base_image": "node:20-alpine",
        "coding_standard": "ESLint + TypeScript Strict",
    },
    "java": {
        "name": "java",
        "extension": ".java",
        "test_framework": "junit",
        "web_framework": "spring",
        "package_manager": "maven",
        "base_image": "eclipse-temurin:21-jre-alpine",
        "coding_standard": "Google Java Style",
    },
}


def get_language_config(language: str) -> Dict[str, Any]:
    """Return config for the given language, case-insensitively.

    Falls back to the Python config with a warning for unknown languages.

    Args:
        language: Language name (e.g. "python", "JavaScript", "JAVA")

    Returns:
        Language config dict with keys: name, extension, test_framework,
        web_framework, package_manager, base_image, coding_standard.
    """
    normalized = language.lower().strip() if language else ""
    config = LANGUAGE_CONFIGS.get(normalized)
    if config is None:
        logger.warning(
            "Unknown language %r — falling back to Python config.", language
        )
        return LANGUAGE_CONFIGS["python"]
    return config
