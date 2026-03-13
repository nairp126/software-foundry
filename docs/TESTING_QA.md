# Testing & Quality Assurance

The Autonomous Software Foundry includes comprehensive automated testing and quality assurance capabilities to ensure generated code meets high standards before deployment.

## Overview

The testing and QA system consists of two main components:

1. **Test Generator** - Automatically generates unit tests for code
2. **Quality Gates** - Enforces quality standards through linting, type checking, and security scanning

## Test Generator

### Features

- **Automatic Test Generation**: Creates unit tests for generated code
- **Framework Selection**: Chooses appropriate testing framework based on language and tech stack
- **Coverage Analysis**: Estimates code coverage and ensures 80% minimum threshold
- **Multiple Language Support**: Python, JavaScript, TypeScript, Java

### Supported Test Frameworks

| Language   | Default Framework | Alternatives |
|------------|------------------|--------------|
| Python     | pytest           | -            |
| JavaScript | Jest             | Vitest, Mocha|
| TypeScript | Jest             | Vitest       |
| Java       | JUnit            | -            |

### Usage Example

```python
from foundry.testing.test_generator import TestGenerator

# Initialize generator
generator = TestGenerator()

# Select framework
framework = generator.select_framework("python")

# Generate tests
test_code = await generator.generate_unit_tests(
    code="def add(a, b): return a + b",
    filename="calculator.py",
    language="python",
    framework=framework
)

# Analyze coverage
coverage = await generator.analyze_coverage(
    source_files={"calculator.py": source_code},
    test_files={"test_calculator.py": test_code},
    language="python"
)

print(f"Coverage: {coverage.coverage_percentage}%")
print(f"Meets threshold: {coverage.meets_threshold}")
```

### Test Generation Process

1. **Framework Selection**: Automatically selects the best testing framework
2. **Test Creation**: Generates comprehensive unit tests including:
   - Tests for all public functions/methods
   - Edge cases and boundary conditions
   - Error handling scenarios
   - Descriptive test names and assertions
3. **Coverage Analysis**: Estimates coverage and identifies gaps
4. **Quality Validation**: Ensures tests meet minimum 80% coverage threshold

## Quality Gates

### Features

- **Linting**: Code style and convention checking
- **Type Checking**: Static type analysis
- **Security Scanning**: Vulnerability and secret detection
- **Automated Enforcement**: Blocks deployment if quality gates fail

### Security Scanning

The security scanner detects:

- **Hardcoded Secrets**:
  - API keys
  - Passwords
  - AWS credentials
  - Database URLs
  - Private keys
  - Auth tokens

- **Common Vulnerabilities**:
  - SQL injection risks
  - XSS vulnerabilities
  - Insecure dependencies
  - Unsafe code patterns

### Linting Support

| Language   | Linter   |
|------------|----------|
| Python     | Pylint   |
| JavaScript | ESLint   |
| TypeScript | ESLint   |
| Ruby       | Rubocop  |

### Type Checking Support

| Language   | Type Checker |
|------------|--------------|
| Python     | mypy         |
| TypeScript | tsc          |

### Usage Example

```python
from foundry.testing.quality_gates import QualityGates

# Initialize quality gates
quality_gates = QualityGates()

# Run all quality gates
result = await quality_gates.run_quality_gates(
    code_files={"main.py": code},
    language="python",
    project_path="/path/to/project"
)

# Check results
if result.passed:
    print("✓ All quality gates passed!")
else:
    print(f"✗ Quality gates failed:")
    print(result.summary)
    print(f"Linting issues: {len(result.lint_issues)}")
    print(f"Type issues: {len(result.type_issues)}")
    print(f"Security issues: {len(result.security_issues)}")
```

### Quality Gate Results

Quality gates return a comprehensive result including:

- **Overall Status**: Pass/fail for deployment
- **Linting Status**: Code style compliance
- **Type Checking Status**: Type safety validation
- **Security Status**: Vulnerability assessment
- **Detailed Issues**: Line-by-line issue reports
- **Summary**: Human-readable summary of results

### Security Issue Severity Levels

- **CRITICAL**: Immediate security risk (blocks deployment)
- **HIGH**: Serious security concern (blocks deployment)
- **MEDIUM**: Moderate security issue (warning)
- **LOW**: Minor security concern (informational)
- **INFO**: Security best practice suggestion

## Integration with Engineering Agent

The Engineering Agent automatically integrates testing and quality assurance:

```python
from foundry.agents.engineer import EngineerAgent

# Initialize agent
engineer = EngineerAgent()

# Generate code (automatically includes tests and quality checks)
result = await engineer.generate_code(architecture_content)

# Result includes:
# - Generated code files
# - Generated test files
# - Quality gate results
# - Integration report
```

### Workflow

1. **Code Generation**: Engineer generates source code
2. **Test Generation**: Automatically creates unit tests
3. **Quality Gates**: Runs linting, type checking, and security scans
4. **Validation**: Ensures all gates pass before proceeding
5. **Reporting**: Provides comprehensive quality report

## Configuration

### Coverage Threshold

Default minimum coverage: **80%**

Can be configured in test generator:

```python
generator = TestGenerator()
generator.COVERAGE_THRESHOLD = 90.0  # Require 90% coverage
```

### Quality Gate Enforcement

Quality gates enforce the following rules:

- **Linting**: All linting issues must be resolved
- **Type Checking**: All type errors must be fixed
- **Security**: No CRITICAL or HIGH severity issues allowed

## Best Practices

### For Test Generation

1. **Write Testable Code**: Keep functions small and focused
2. **Use Type Hints**: Helps generate better tests
3. **Document Functions**: Improves test generation quality
4. **Handle Errors**: Include error handling for better test coverage

### For Quality Gates

1. **Fix Issues Early**: Address quality issues during development
2. **Use Environment Variables**: Never hardcode secrets
3. **Follow Conventions**: Adhere to language-specific style guides
4. **Enable Type Checking**: Use type hints/annotations

### For Security

1. **Environment Variables**: Store secrets in environment variables
2. **Secret Management**: Use proper secret management services
3. **Input Validation**: Always validate and sanitize inputs
4. **Dependency Scanning**: Keep dependencies up to date

## Examples

See `examples/testing_demo.py` for comprehensive demonstrations of:

- Automated test generation
- Quality gate enforcement
- Security scanning
- Coverage analysis

## Requirements Validation

This implementation validates the following requirements:

- **17.1**: Automated test generation with 80% minimum coverage
- **17.3**: Test framework selection based on technology stack
- **17.4**: Linting and type checking integration
- **17.6**: Quality gate enforcement before deployment

## Future Enhancements

Planned improvements:

- Integration tests generation
- Performance test generation
- Load test generation
- Visual regression testing
- Mutation testing
- Advanced security scanning (SAST/DAST)
