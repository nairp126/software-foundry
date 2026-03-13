# Architect Agent: Code Organization & Documentation

## Overview

The Architect Agent has been enhanced with comprehensive code organization and documentation capabilities. These features enable the agent to generate well-structured project layouts, document architectural decisions, and track rationale and trade-offs for design choices.

## Features

### 1. File Structure Generation

The `organize_file_structure()` method generates project file structures following industry best practices for the selected technology stack.

**Capabilities:**
- Separation of concerns (MVC, Clean Architecture, etc.)
- Configuration management (environment files, config directories)
- Testing structure (unit, integration, e2e tests)
- Documentation placement (README, API docs, architecture docs)
- Build and deployment files (Dockerfile, CI/CD configs)
- Framework-specific organization patterns

**Example Usage:**

```python
from foundry.agents.architect import ArchitectAgent

architect = ArchitectAgent(model_name="qwen2.5-coder:7b")

architecture = {
    "pattern": "microservices",
    "technology_stack": {
        "frontend": "React",
        "backend": "Node.js",
        "database": "PostgreSQL"
    }
}

tech_stack = {
    "frontend": "React with TypeScript",
    "backend": "Node.js with Express",
    "database": "PostgreSQL"
}

file_structure = await architect.organize_file_structure(architecture, tech_stack)
```

**Output Structure:**

```json
{
    "root_structure": {
        "directories": [
            {
                "path": "src/",
                "purpose": "Main source code directory",
                "subdirectories": [...]
            }
        ],
        "files": [
            {
                "path": "README.md",
                "purpose": "Project documentation",
                "template": "basic"
            }
        ]
    },
    "conventions": {
        "naming": "kebab-case for files, PascalCase for classes",
        "structure_pattern": "Feature-based organization",
        "test_location": "Co-located with source files"
    }
}
```

### 2. Architectural Decision Records (ADRs)

The `document_architectural_decisions()` method creates comprehensive ADRs following the standard format.

**ADR Components:**
1. **Context**: What issue are we addressing?
2. **Decision**: What change are we proposing?
3. **Rationale**: Why did we choose this approach?
4. **Consequences**: What are the positive and negative outcomes?
5. **Alternatives Considered**: What other options were evaluated?
6. **Trade-offs**: What are we optimizing for vs sacrificing?

**Example Usage:**

```python
adrs = await architect.document_architectural_decisions(
    architecture=architecture,
    tech_stack=tech_stack,
    requirements=prd_content
)
```

**Output Structure:**

```json
{
    "decisions": [
        {
            "id": "ADR-001",
            "title": "Selection of React for Frontend",
            "status": "accepted",
            "context": "Need a modern, component-based UI framework...",
            "decision": "Use React with TypeScript for frontend development",
            "rationale": "Large ecosystem, strong typing, team expertise...",
            "consequences": {
                "positive": ["Fast development", "Rich ecosystem"],
                "negative": ["Learning curve for new developers"]
            },
            "alternatives": ["Vue.js", "Angular", "Svelte"],
            "trade_offs": {
                "optimizing_for": ["Developer productivity", "Maintainability"],
                "sacrificing": ["Bundle size", "Initial learning curve"]
            }
        }
    ]
}
```

### 3. Rationale and Trade-off Tracking

The `track_rationale_and_tradeoffs()` method provides detailed analysis of architectural decisions.

**Analysis Dimensions:**
- Performance implications
- Scalability considerations
- Maintainability impact
- Cost implications (development and operational)
- Team expertise and learning curve
- Time-to-market impact
- Security considerations
- Flexibility for future changes

**Example Usage:**

```python
decision_context = {
    "decision": "Use microservices architecture",
    "requirements": "High scalability, independent deployment",
    "constraints": "Team size: 5 developers, Timeline: 6 months"
}

analysis = await architect.track_rationale_and_tradeoffs(
    decision_id="ADR-001",
    decision_context=decision_context
)
```

**Output Structure:**

```json
{
    "decision_id": "ADR-001",
    "rationale": {
        "primary_drivers": ["Performance", "Scalability"],
        "detailed_reasoning": "Detailed explanation...",
        "supporting_evidence": ["Benchmark data", "Industry practices"]
    },
    "trade_offs": {
        "dimensions": [
            {
                "dimension": "Performance",
                "impact": "positive",
                "score": 8,
                "explanation": "Optimized for high throughput..."
            },
            {
                "dimension": "Complexity",
                "impact": "negative",
                "score": -3,
                "explanation": "Introduces additional operational overhead..."
            }
        ],
        "overall_assessment": "Net positive with manageable complexity",
        "risk_factors": ["Operational complexity", "Team learning curve"]
    },
    "future_implications": {
        "enables": ["Horizontal scaling", "Independent deployments"],
        "constrains": ["Requires distributed tracing", "More complex debugging"]
    }
}
```

### 4. Comprehensive Design Generation

The `generate_comprehensive_design()` method combines all features into a complete design package.

**Example Usage:**

```python
prd_content = """
Product Requirements Document: Task Management System

Functional Requirements:
1. User authentication and authorization
2. Create, read, update, delete tasks
3. Assign tasks to team members
...
"""

comprehensive_design = await architect.generate_comprehensive_design(prd_content)
```

**Output Structure:**

```json
{
    "architecture": { ... },
    "file_structure": { ... },
    "architectural_decisions": { ... },
    "metadata": {
        "generated_at": "2024-01-15T10:30:00Z",
        "agent": "architect",
        "model": "qwen2.5-coder:7b"
    }
}
```

## Best Practices

### File Structure Organization

1. **Separation of Concerns**: Organize code by feature or layer
2. **Configuration Management**: Keep environment-specific configs separate
3. **Testing Structure**: Co-locate tests with source code or use dedicated test directories
4. **Documentation**: Include README, API docs, and architecture diagrams
5. **Build Files**: Include Dockerfile, CI/CD configs, and dependency management files

### Architectural Decision Documentation

1. **Be Specific**: Clearly state the decision and its context
2. **Document Alternatives**: Show what options were considered
3. **Explain Trade-offs**: Be honest about pros and cons
4. **Update Status**: Mark decisions as proposed, accepted, deprecated, or superseded
5. **Link to Requirements**: Reference specific requirements that drove the decision

### Trade-off Analysis

1. **Consider Multiple Dimensions**: Performance, scalability, maintainability, cost, etc.
2. **Quantify When Possible**: Use scores or metrics to compare options
3. **Think Long-term**: Consider future implications and constraints
4. **Document Risks**: Identify potential issues and mitigation strategies
5. **Revisit Decisions**: Update analysis as new information becomes available

## Integration with Other Agents

The Architect Agent's organization and documentation features integrate with:

- **Product Manager Agent**: Uses PRD content to inform architectural decisions
- **Engineering Agent**: Provides file structure and conventions for code generation
- **DevOps Agent**: Informs infrastructure decisions and deployment strategies
- **Code Review Agent**: Uses ADRs to validate code against architectural decisions

## Requirements Satisfied

This implementation satisfies the following requirements from the spec:

- **Requirement 3.4**: File structure generation following best practices
- **Requirement 3.5**: Architectural decision documentation with rationale and trade-offs

## Testing

Run the test suite:

```bash
pytest tests/test_architect_organization.py -v
```

Run the demo script:

```bash
python examples/architect_organization_demo.py
```

## Configuration

The Architect Agent uses the LLM configuration from `src/foundry/config.py`:

```python
# Default model for Architect Agent
ollama_model_name: str = "qwen2.5-coder:7b"

# For production, consider using larger models:
# - qwen2.5-coder:14b (better quality, requires 12GB VRAM)
# - qwen2.5-coder:32b (best quality, requires 24GB VRAM)
```

## Future Enhancements

Potential improvements for future iterations:

1. **Visual Diagrams**: Generate Mermaid.js diagrams for architecture visualization
2. **ADR Templates**: Support custom ADR templates for different organizations
3. **Decision History**: Track evolution of decisions over time
4. **Impact Analysis**: Analyze impact of changing architectural decisions
5. **Best Practice Validation**: Automatically validate file structure against industry standards
6. **Cost Estimation**: Include cost implications in trade-off analysis
7. **Team Collaboration**: Support multi-stakeholder decision-making workflows

## References

- [Architectural Decision Records (ADRs)](https://adr.github.io/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Project Structure Best Practices](https://github.com/goldbergyoni/nodebestpractices)
- [Trade-off Analysis in Software Architecture](https://www.sei.cmu.edu/our-work/software-architecture/)
