"""Validate project setup and structure."""

import os
import sys
from pathlib import Path


def check_file_exists(filepath: str) -> bool:
    """Check if a file exists."""
    exists = Path(filepath).exists()
    status = "✓" if exists else "✗"
    print(f"{status} {filepath}")
    return exists


def check_directory_exists(dirpath: str) -> bool:
    """Check if a directory exists."""
    exists = Path(dirpath).is_dir()
    status = "✓" if exists else "✗"
    print(f"{status} {dirpath}/")
    return exists


def main():
    """Run validation checks."""
    print("Validating Autonomous Software Foundry Setup\n")
    
    all_checks = []
    
    print("Core Configuration Files:")
    all_checks.append(check_file_exists("pyproject.toml"))
    all_checks.append(check_file_exists("requirements.txt"))
    all_checks.append(check_file_exists("requirements-dev.txt"))
    all_checks.append(check_file_exists(".env.example"))
    all_checks.append(check_file_exists(".gitignore"))
    
    print("\nDocker Configuration:")
    all_checks.append(check_file_exists("Dockerfile"))
    all_checks.append(check_file_exists("docker-compose.yml"))
    all_checks.append(check_file_exists(".dockerignore"))
    
    print("\nDatabase Configuration:")
    all_checks.append(check_file_exists("alembic.ini"))
    all_checks.append(check_directory_exists("alembic"))
    all_checks.append(check_file_exists("alembic/env.py"))
    
    print("\nSource Code Structure:")
    all_checks.append(check_directory_exists("src/foundry"))
    all_checks.append(check_file_exists("src/foundry/__init__.py"))
    all_checks.append(check_file_exists("src/foundry/main.py"))
    all_checks.append(check_file_exists("src/foundry/config.py"))
    all_checks.append(check_file_exists("src/foundry/database.py"))
    all_checks.append(check_file_exists("src/foundry/redis_client.py"))
    all_checks.append(check_file_exists("src/foundry/celery_app.py"))
    
    print("\nAgent Structure:")
    all_checks.append(check_directory_exists("src/foundry/agents"))
    all_checks.append(check_directory_exists("src/foundry/api"))
    all_checks.append(check_directory_exists("src/foundry/models"))
    
    print("\nTest Structure:")
    all_checks.append(check_directory_exists("tests"))
    all_checks.append(check_file_exists("tests/__init__.py"))
    all_checks.append(check_file_exists("tests/conftest.py"))
    
    print("\nCI/CD Configuration:")
    all_checks.append(check_directory_exists(".github/workflows"))
    all_checks.append(check_file_exists(".github/workflows/ci.yml"))
    all_checks.append(check_file_exists(".pre-commit-config.yaml"))
    
    print("\nDocumentation:")
    all_checks.append(check_file_exists("README.md"))
    all_checks.append(check_file_exists("Makefile"))
    
    print("\n" + "="*50)
    passed = sum(all_checks)
    total = len(all_checks)
    print(f"Validation Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("✓ All checks passed! Project setup is complete.")
        return 0
    else:
        print(f"✗ {total - passed} checks failed. Please review the setup.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
