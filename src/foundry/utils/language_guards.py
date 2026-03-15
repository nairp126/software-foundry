"""Language-aware mismatch detection and recovery prompt generation.

These guards replace the inline JS_PATTERNS regex gates that were scattered
across agents. They are language-neutral: detecting a mismatch means the code
is in a *different* language than expected, not that non-Python code is bad.
"""

import re
import logging
from typing import Dict, Pattern

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language signature patterns
# Each entry is a list of regex patterns that are *strongly indicative* of
# that language. A pattern match means "this code looks like <language>".
# ---------------------------------------------------------------------------
_LANGUAGE_SIGNATURES: Dict[str, list] = {
    "python": [
        r"\bdef\s+\w+\s*\(",
        r"\bimport\s+\w+",
        r"\bfrom\s+\w[\w.]+\s+import\b",
        r"\bclass\s+\w+.*:",
        r"\bprint\s*\(",
        r"#.*coding",
        r"\bif\s+__name__\s*==\s*['\"]__main__['\"]",
    ],
    "javascript": [
        r"\bconst\s+\w+\s*=",
        r"\blet\s+\w+\s*=",
        r"\bvar\s+\w+\s*=",
        r"\brequire\s*\(",
        r"\bmodule\.exports\b",
        r"\bexport\s+default\b",
        r"\bexport\s+(?:const|function|class)\b",
        r"=>\s*\{",
        r"\bconsole\.log\s*\(",
        r"\.then\s*\(",
        r"\.catch\s*\(",
    ],
    "typescript": [
        r"\bconst\s+\w+\s*:\s*\w+",
        r"\binterface\s+\w+\s*\{",
        r"\btype\s+\w+\s*=",
        r":\s*(?:string|number|boolean|void|any|unknown|never)\b",
        r"\benum\s+\w+\s*\{",
        r"\bimport\s+type\b",
        r"<\w+(?:,\s*\w+)*>",  # generics
    ],
    "java": [
        r"\bpublic\s+(?:class|interface|enum)\s+\w+",
        r"\bprivate\s+\w+\s+\w+\s*[;(=]",
        r"\bSystem\.out\.print",
        r"\bimport\s+java\.",
        r"\bimport\s+org\.",
        r"@Override\b",
        r"\bvoid\s+\w+\s*\(",
        r"\bString\[\]\s+args\b",
    ],
}

# Pre-compile all patterns for performance
_COMPILED_SIGNATURES: Dict[str, list] = {
    lang: [re.compile(p, re.MULTILINE) for p in patterns]
    for lang, patterns in _LANGUAGE_SIGNATURES.items()
}


def _score_language(code: str) -> Dict[str, int]:
    """Return a hit-count score for each language against the given code."""
    scores: Dict[str, int] = {}
    for lang, patterns in _COMPILED_SIGNATURES.items():
        scores[lang] = sum(1 for p in patterns if p.search(code))
    return scores


def detect_language_mismatch(code: str, expected_language: str) -> bool:
    """Return True if *code* appears to be in a different language than expected.

    The function is language-neutral: passing JavaScript code with
    ``expected_language="javascript"`` returns ``False``.

    Args:
        code: Source code string to inspect.
        expected_language: The language the code is supposed to be in.

    Returns:
        True when a mismatch is detected, False when the code matches or
        when there is insufficient signal to make a determination.
    """
    if not code or not code.strip():
        return False

    normalized_expected = expected_language.lower().strip()
    scores = _score_language(code)

    expected_score = scores.get(normalized_expected, 0)

    # Find the highest-scoring language
    best_lang = max(scores, key=lambda l: scores[l])
    best_score = scores[best_lang]

    # No signal at all — can't determine mismatch
    if best_score == 0:
        return False

    # If the expected language has the highest (or tied) score, no mismatch
    if expected_score >= best_score:
        return False

    # A different language scores higher — mismatch detected
    logger.debug(
        "Language mismatch: expected=%r (score=%d), detected=%r (score=%d)",
        normalized_expected,
        expected_score,
        best_lang,
        best_score,
    )
    return True


def recover_prompt(
    filename: str,
    dirty_code: str,
    target_language: str,
    architecture: str,
) -> str:
    """Build a corrective LLM prompt for a language mismatch.

    Args:
        filename: The file that contains the wrong-language code.
        dirty_code: The incorrectly-generated code.
        target_language: The language the file should be written in.
        architecture: Architecture description for context.

    Returns:
        A non-empty prompt string instructing the LLM to rewrite the code.
    """
    from foundry.utils.language_config import get_language_config

    config = get_language_config(target_language)
    lang_name = config["name"]
    extension = config["extension"]
    framework = config["web_framework"]
    standard = config["coding_standard"]

    return (
        f"CRITICAL CORRECTION REQUIRED\n"
        f"The file '{filename}' was generated in the wrong language.\n"
        f"You MUST rewrite it entirely in {lang_name.title()} "
        f"(file extension: {extension}).\n\n"
        f"Target language: {lang_name}\n"
        f"Preferred framework: {framework}\n"
        f"Coding standard: {standard}\n\n"
        f"Architecture context:\n{architecture}\n\n"
        f"Incorrect code to rewrite:\n```\n{dirty_code}\n```\n\n"
        f"Return ONLY the corrected {lang_name} code for '{filename}'. "
        f"No explanations, no markdown fences."
    )
