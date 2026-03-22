"""Unit tests for the language_config module (Requirement 7)."""

import pytest
from foundry.utils.language_config import LANGUAGE_CONFIGS, get_language_config, LanguageConfig

# Updated fields based on the current dataclass definition
REQUIRED_FIELDS = [
    "name", "extensions", "entry_point", "package_file", 
    "test_pattern", "linters", "test_framework", 
    "base_image", "coding_standard", "web_frameworks"
]
SUPPORTED_LANGUAGES = ["python", "javascript", "typescript", "java"]


class TestLanguageConfigs:
    """Tests for the LANGUAGE_CONFIGS dict and get_language_config()."""

    @pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
    def test_supported_language_returns_config(self, language):
        """Each supported language returns a LanguageConfig object."""
        config = get_language_config(language)
        assert isinstance(config, LanguageConfig)

    @pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
    def test_config_has_all_required_fields(self, language):
        """Each config contains all required dataclass fields."""
        config = get_language_config(language)
        for field in REQUIRED_FIELDS:
            assert hasattr(config, field), f"Field '{field}' missing from {language} config"

    def test_python_config_values(self):
        config = get_language_config("python")
        assert config.name == "python"
        assert ".py" in config.extensions
        assert config.test_framework == "pytest"
        assert "FastAPI" in config.web_frameworks
        assert config.package_file == "requirements.txt"

    def test_javascript_config_values(self):
        config = get_language_config("javascript")
        assert config.name == "javascript"
        assert ".js" in config.extensions
        assert config.test_framework == "jest"
        assert "Express" in config.web_frameworks
        assert config.package_file == "package.json"

    def test_typescript_config_values(self):
        config = get_language_config("typescript")
        assert config.name == "typescript"
        assert ".ts" in config.extensions
        assert config.test_framework == "jest"
        assert "Express" in config.web_frameworks
        assert config.package_file == "package.json"

    def test_java_config_values(self):
        config = get_language_config("java")
        assert config.name == "java"
        assert ".java" in config.extensions
        assert config.test_framework == "JUnit"
        assert "Spring Boot" in config.web_frameworks
        assert config.package_file == "pom.xml"

    def test_case_insensitive_lookup_upper(self):
        """get_language_config is case-insensitive."""
        config = get_language_config("PYTHON")
        assert config.name == "python"

    def test_case_insensitive_lookup_mixed(self):
        config = get_language_config("JavaScript")
        assert config.name == "javascript"

    def test_case_insensitive_lookup_java_upper(self):
        config = get_language_config("JAVA")
        assert config.name == "java"

    def test_unknown_language_falls_back_to_python(self):
        """Unknown language returns Python config (Req 7.5)."""
        config = get_language_config("cobol")
        assert config.name == "python", (
            "Unknown language should fall back to Python config"
        )

    def test_empty_string_falls_back_to_python(self):
        """Empty string falls back to Python config."""
        config = get_language_config("")
        assert config.name == "python"

    def test_none_like_empty_falls_back_to_python(self):
        """Whitespace-only string falls back to Python config."""
        config = get_language_config("   ")
        assert config.name == "python"

    def test_language_configs_dict_has_all_four_languages(self):
        """LANGUAGE_CONFIGS contains exactly the four supported languages."""
        for lang in SUPPORTED_LANGUAGES:
            assert lang in LANGUAGE_CONFIGS
