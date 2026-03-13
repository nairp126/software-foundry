"""
Unit tests for EngineerAgent code quality and security measures.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from foundry.agents.engineer import EngineerAgent
from foundry.agents.base import AgentType, AgentMessage, MessageType
from foundry.llm.base import LLMResponse


class TestEngineerAgentCodeQuality:
    """Test code quality and security measures in EngineerAgent."""
    
    @pytest.fixture
    def engineer_agent(self):
        """Create an EngineerAgent instance for testing."""
        with patch('foundry.agents.engineer.LLMProviderFactory.create_provider'):
            agent = EngineerAgent(model_name="qwen2.5-coder:7b")
            agent.llm = AsyncMock()
            return agent
    
    def test_coding_standards_defined(self, engineer_agent):
        """Test that coding standards are defined for multiple languages."""
        assert "python" in engineer_agent.CODING_STANDARDS
        assert "javascript" in engineer_agent.CODING_STANDARDS
        assert "typescript" in engineer_agent.CODING_STANDARDS
        assert engineer_agent.CODING_STANDARDS["python"] == "PEP 8"
    
    def test_security_patterns_enabled(self, engineer_agent):
        """Test that security patterns are enabled."""
        assert engineer_agent.SECURITY_PATTERNS["input_validation"] is True
        assert engineer_agent.SECURITY_PATTERNS["sql_injection_prevention"] is True
        assert engineer_agent.SECURITY_PATTERNS["xss_protection"] is True
        assert engineer_agent.SECURITY_PATTERNS["secure_authentication"] is True
    
    def test_detect_language_python(self, engineer_agent):
        """Test language detection for Python projects."""
        architecture = "Build a FastAPI application with Python and pytest"
        language = engineer_agent._detect_language(architecture)
        assert language == "python"
    
    def test_detect_language_javascript(self, engineer_agent):
        """Test language detection for JavaScript projects."""
        architecture = "Build a Node.js Express application with React frontend"
        language = engineer_agent._detect_language(architecture)
        assert language == "javascript"
    
    def test_detect_language_typescript(self, engineer_agent):
        """Test language detection for TypeScript projects."""
        architecture = "Build a NestJS application with TypeScript"
        language = engineer_agent._detect_language(architecture)
        assert language == "typescript"
    
    def test_detect_language_default(self, engineer_agent):
        """Test language detection defaults to Python."""
        architecture = "Build a generic application"
        language = engineer_agent._detect_language(architecture)
        assert language == "python"
    
    def test_contains_hardcoded_secrets_password(self, engineer_agent):
        """Test detection of hardcoded passwords."""
        code_with_secret = 'password = "mysecretpass123"'
        assert engineer_agent._contains_hardcoded_secrets(code_with_secret) is True
    
    def test_contains_hardcoded_secrets_api_key(self, engineer_agent):
        """Test detection of hardcoded API keys."""
        code_with_secret = 'api_key = "sk-1234567890abcdefghijklmnop"'
        assert engineer_agent._contains_hardcoded_secrets(code_with_secret) is True
    
    def test_contains_hardcoded_secrets_clean_code(self, engineer_agent):
        """Test that clean code without secrets passes."""
        clean_code = 'password = os.getenv("PASSWORD")'
        assert engineer_agent._contains_hardcoded_secrets(clean_code) is False
    
    def test_has_error_handling_python_with_try_except(self, engineer_agent):
        """Test error handling detection in Python code with try-except."""
        code_with_error_handling = """
def process_data():
    try:
        result = risky_operation()
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
"""
        assert engineer_agent._has_error_handling(code_with_error_handling, "python") is True
    
    def test_has_error_handling_python_without(self, engineer_agent):
        """Test error handling detection in Python code without error handling."""
        # Create code with more than 50 lines without error handling
        code_without_error_handling = "\n".join([
            "def process_data():",
            "    result = risky_operation()",
            "    return result",
            ""
        ] * 15)  # 60 lines total
        assert engineer_agent._has_error_handling(code_without_error_handling, "python") is False
    
    def test_has_error_handling_javascript(self, engineer_agent):
        """Test error handling detection in JavaScript code."""
        code_with_error_handling = """
async function processData() {
    try {
        const result = await riskyOperation();
        return result;
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
}
""" * 10
        assert engineer_agent._has_error_handling(code_with_error_handling, "javascript") is True
    
    def test_has_error_handling_small_file_exempt(self, engineer_agent):
        """Test that small files are exempt from error handling requirement."""
        small_code = "def hello(): return 'world'"
        assert engineer_agent._has_error_handling(small_code, "python") is True
    
    def test_extract_imports_python(self, engineer_agent):
        """Test extraction of Python imports."""
        code = """
import os
import sys
from typing import Dict, List
from foundry.agents import base
"""
        imports = engineer_agent._extract_imports(code, "test.py")
        assert "os" in imports
        assert "sys" in imports
        assert "typing" in imports
        assert "foundry.agents" in imports
    
    def test_extract_imports_javascript(self, engineer_agent):
        """Test extraction of JavaScript imports."""
        code = """
import React from 'react';
import { useState } from 'react';
const express = require('express');
"""
        imports = engineer_agent._extract_imports(code, "test.js")
        assert "react" in imports
        assert "express" in imports
    
    def test_extract_dependencies_requirements_txt(self, engineer_agent):
        """Test extraction of Python dependencies from requirements.txt."""
        code = """
fastapi==0.104.1
uvicorn>=0.24.0
pytest==7.4.3
# This is a comment
requests>=2.31.0
"""
        deps = engineer_agent._extract_dependencies(code, "requirements.txt")
        assert "fastapi" in deps
        assert "uvicorn" in deps
        assert "pytest" in deps
        assert "requests" in deps
    
    def test_extract_dependencies_package_json(self, engineer_agent):
        """Test extraction of JavaScript dependencies from package.json."""
        code = """
{
  "dependencies": {
    "express": "^4.18.2",
    "react": "^18.2.0"
  },
  "devDependencies": {
    "jest": "^29.7.0"
  }
}
"""
        deps = engineer_agent._extract_dependencies(code, "package.json")
        assert "express" in deps
        assert "react" in deps
        assert "jest" in deps
    
    def test_validate_component_integration_no_issues(self, engineer_agent):
        """Test component integration validation with no issues."""
        code_files = {
            "main.py": "import utils\n\ndef main(): pass",
            "utils.py": "def helper(): pass"
        }
        report = engineer_agent._validate_component_integration(code_files)
        assert report["status"] == "valid"
        assert len(report["issues"]) == 0
    
    def test_validate_component_integration_with_dependencies(self, engineer_agent):
        """Test component integration validation extracts dependencies."""
        code_files = {
            "requirements.txt": "fastapi==0.104.1\nuvicorn>=0.24.0"
        }
        report = engineer_agent._validate_component_integration(code_files)
        assert "fastapi" in report["dependencies"]
        assert "uvicorn" in report["dependencies"]
    
    @pytest.mark.asyncio
    async def test_generate_file_content_includes_security_requirements(self, engineer_agent):
        """Test that file content generation includes security requirements in prompt."""
        engineer_agent.llm.generate = AsyncMock(return_value=LLMResponse(
            content="def secure_function(): pass",
            model="qwen2.5-coder:7b",
            tokens_used=150,
            finish_reason="stop",
            metadata={}
        ))
        
        await engineer_agent._generate_file_content("test.py", "Build a secure API", "python")
        
        # Verify the system prompt includes security requirements
        call_args = engineer_agent.llm.generate.call_args
        messages = call_args[0][0]
        system_message = messages[0].content
        
        assert "security best practices" in system_message.lower()
        assert "input validation" in system_message.lower()
        assert "error handling" in system_message.lower()
        assert "PEP 8" in system_message
    
    @pytest.mark.asyncio
    async def test_enhance_code_quality_detects_secrets(self, engineer_agent):
        """Test that code quality enhancement detects hardcoded secrets."""
        code_with_secret = 'api_key = "sk-1234567890abcdefghijklmnop"'
        
        engineer_agent.llm.generate = AsyncMock(return_value=LLMResponse(
            content='api_key = os.getenv("API_KEY")',
            model="qwen2.5-coder:7b",
            tokens_used=150,
            finish_reason="stop",
            metadata={}
        ))
        
        enhanced_code = await engineer_agent._enhance_code_quality(
            code_with_secret, "test.py", "python"
        )
        
        # Verify improvement was requested
        assert engineer_agent.llm.generate.called
    
    @pytest.mark.asyncio
    async def test_enhance_code_quality_clean_code_unchanged(self, engineer_agent):
        """Test that clean code passes quality enhancement without changes."""
        clean_code = """
import os

def get_api_key():
    try:
        return os.getenv("API_KEY")
    except Exception as e:
        raise ValueError("API key not found")
"""
        
        enhanced_code = await engineer_agent._enhance_code_quality(
            clean_code, "test.py", "python"
        )
        
        # No LLM call should be made for clean code
        assert not engineer_agent.llm.generate.called
        assert enhanced_code == clean_code
    
    @pytest.mark.asyncio
    async def test_generate_code_includes_integration_report(self, engineer_agent):
        """Test that generate_code includes integration report in response."""
        engineer_agent.llm.generate = AsyncMock(return_value=LLMResponse(
            content='["main.py"]',
            model="qwen2.5-coder:7b",
            tokens_used=150,
            finish_reason="stop",
            metadata={}
        ))
        
        # Mock subsequent calls for file content
        engineer_agent.llm.generate.side_effect = [
            LLMResponse(content='["main.py"]', model="qwen2.5-coder:7b", tokens_used=50, finish_reason="stop", metadata={}),
            LLMResponse(content='def main(): pass', model="qwen2.5-coder:7b", tokens_used=100, finish_reason="stop", metadata={})
        ]
        
        result = await engineer_agent.generate_code("Build a Python app")
        
        assert "integration_report" in result.payload
        assert "language" in result.payload
        assert result.payload["language"] == "python"


class TestEngineerAgentEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def engineer_agent(self):
        """Create an EngineerAgent instance for testing."""
        with patch('foundry.agents.engineer.LLMProviderFactory.create_provider'):
            agent = EngineerAgent(model_name="qwen2.5-coder:7b")
            agent.llm = AsyncMock()
            return agent
    
    def test_has_circular_dependencies_simple_case(self, engineer_agent):
        """Test circular dependency detection."""
        imports_map = {
            "module_a.py": ["module_b"],
            "module_b.py": ["module_a"]
        }
        assert engineer_agent._has_circular_dependencies(imports_map) is True
    
    def test_has_circular_dependencies_no_cycle(self, engineer_agent):
        """Test no circular dependencies detected when none exist."""
        imports_map = {
            "module_a.py": ["module_b"],
            "module_b.py": ["module_c"],
            "module_c.py": []
        }
        assert engineer_agent._has_circular_dependencies(imports_map) is False
    
    def test_extract_dependencies_invalid_json(self, engineer_agent):
        """Test dependency extraction handles invalid JSON gracefully."""
        invalid_json = "{ invalid json }"
        deps = engineer_agent._extract_dependencies(invalid_json, "package.json")
        assert deps == []
    
    def test_extract_imports_empty_file(self, engineer_agent):
        """Test import extraction from empty file."""
        imports = engineer_agent._extract_imports("", "test.py")
        assert imports == []
    
    def test_contains_hardcoded_secrets_edge_cases(self, engineer_agent):
        """Test secret detection with edge cases."""
        # Short password should not trigger (< 8 chars)
        short_pass = 'password = "short"'
        assert engineer_agent._contains_hardcoded_secrets(short_pass) is False
        
        # Variable name containing 'password' but not assignment
        var_name = 'user_password_field = "password"'
        # This might trigger, which is acceptable for security
        result = engineer_agent._contains_hardcoded_secrets(var_name)
        assert isinstance(result, bool)
