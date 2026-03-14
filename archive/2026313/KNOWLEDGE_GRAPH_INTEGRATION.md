# Knowledge Graph Integration Guide

## Overview

The Knowledge Graph is now fully integrated into the agent workflow, providing semantic code understanding and context-aware decision making.

## What's Integrated

### 1. Automatic Ingestion Trigger
**Location**: `src/foundry/orchestrator.py` → `_run_engineer()`

After the Engineer agent generates code, the orchestrator automatically:
- Connects to Neo4j
- Parses all generated Python files using AST
- Creates nodes for Functions, Classes, and Modules
- Establishes relationships (CALLS, DEPENDS_ON, IMPORTS)
- Stores in Neo4j for semantic queries

```python
# Automatic ingestion after code generation
await ingest_project(
    kg_service=self.kg_service,
    project_id=project_id,
    project_path=base_path,
    project_name=f"Project-{project_id}"
)
```

### 2. Knowledge Graph Tools for Agents
**Location**: `src/foundry/tools/knowledge_graph_tools.py`

All agents now have access to KG tools:


#### Available Tools:

- `find_function_dependencies()` - Find all dependencies of a function
- `analyze_change_impact()` - Analyze blast radius of changes
- `find_callers()` - Find who calls a specific function
- `search_by_pattern()` - Search components by regex pattern
- `get_component_context()` - Get comprehensive context for a component
- `get_file_components()` - List all components in a file
- `get_high_complexity_components()` - Find complex functions

### 3. Reflexion Engine Integration
**Location**: `src/foundry/agents/reflexion.py`

The Reflexion Engine now uses the Knowledge Graph for impact analysis:

```python
async def analyze_impact_with_kg(
    self,
    project_id: str,
    component_name: str,
    error_analysis: ErrorAnalysis
) -> Dict[str, Any]:
    """Analyze blast radius of errors using Knowledge Graph."""
```

**Features**:
- Identifies affected components when an error occurs
- Calculates "blast radius" (how many components are impacted)
- Finds all callers and dependencies
- Assigns risk levels (low/medium/high)

### 4. Agent Integration
**Agents with KG Access**:
- ✅ Engineer Agent - Context-aware code generation
- ✅ Architect Agent - Architecture decisions based on existing patterns
- ✅ Reflexion Agent - Impact analysis for error fixes



## How It Works

### Workflow

```
1. User submits requirements
   ↓
2. Product Manager → Architect → Engineer
   ↓
3. Engineer generates code
   ↓
4. 🔥 AUTOMATIC INGESTION 🔥
   - Parse Python files with AST
   - Extract functions, classes, imports
   - Build dependency graph
   - Store in Neo4j
   ↓
5. Code Review → Reflexion (if needed)
   ↓
6. Reflexion uses KG for impact analysis
   - Query affected components
   - Calculate blast radius
   - Inform fix strategy
   ↓
7. DevOps → Deployment
```

### Example: Impact Analysis

When Reflexion detects an error in `calculate_total()`:

```python
impact = await kg_tools.analyze_change_impact(
    project_id="abc-123",
    component_name="calculate_total",
    max_depth=3
)

# Returns:
{
    "affected_components": [
        {"name": "process_order", "type": "Function"},
        {"name": "generate_invoice", "type": "Function"},
        {"name": "OrderService", "type": "Class"}
    ],
    "blast_radius": 3,
    "risk_level": "medium"
}
```



## Usage Examples

### For Agent Developers

#### 1. Query Dependencies Before Modifying Code

```python
# In Engineer Agent
if self.kg_tools:
    await self.kg_tools.connect()
    
    # Check what depends on this function
    dependencies = await self.kg_tools.find_function_dependencies(
        project_id=project_id,
        function_name="user_authentication",
        max_depth=2
    )
    
    # Use this context to inform code generation
    context = self.kg_tools.format_for_llm(dependencies)
    prompt += f"\n\nExisting dependencies:\n{context}"
    
    await self.kg_tools.disconnect()
```

#### 2. Find High-Risk Components

```python
# Find complex functions that need refactoring
complex_components = await kg_tools.get_high_complexity_components(
    project_id=project_id,
    min_complexity=15
)

for component in complex_components:
    print(f"{component['name']}: complexity {component['complexity']}")
```

#### 3. Search for Patterns

```python
# Find all authentication-related functions
auth_functions = await kg_tools.search_by_pattern(
    project_id=project_id,
    pattern=".*auth.*",
    node_type="Function"
)
```



## Configuration

### Environment Variables

Ensure these are set in your `.env`:

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### Docker Setup

Neo4j is already configured in `docker-compose.yml`:

```yaml
neo4j:
  image: neo4j:5.16.0
  ports:
    - "7474:7474"  # HTTP
    - "7687:7687"  # Bolt
  environment:
    NEO4J_AUTH: neo4j/foundry_neo4j_pass
```

## Testing

### Manual Test

```python
from foundry.tools.knowledge_graph_tools import kg_tools

# Connect
await kg_tools.connect()

# Test query
dependencies = await kg_tools.find_function_dependencies(
    project_id="test-project",
    function_name="main",
    max_depth=2
)

print(dependencies)

# Disconnect
await kg_tools.disconnect()
```

### Run Integration Tests

```bash
pytest tests/test_knowledge_graph.py -v
```



## What's Still Missing (Future Enhancements)

### 1. Proactive Agent Queries
Currently agents have KG tools but don't automatically use them. Future:
- Engineer should query existing patterns before generating new code
- Architect should check for similar architectures in past projects
- Code Review should verify against dependency constraints

### 2. Real-time Updates
Currently ingestion happens once after code generation. Future:
- Incremental updates when code changes
- Real-time sync during development
- Version tracking in the graph

### 3. Cross-Project Learning
Currently each project is isolated. Future:
- Query patterns across all projects
- Learn from successful architectures
- Identify anti-patterns

### 4. Advanced Queries
Future query capabilities:
- "Find all functions that handle user data"
- "Show me the data flow from API to database"
- "Which components have no test coverage?"
- "Find circular dependencies"

## Troubleshooting

### Neo4j Connection Issues

```bash
# Check if Neo4j is running
docker ps | grep neo4j

# View Neo4j logs
docker logs foundry-neo4j

# Restart Neo4j
docker-compose restart neo4j
```

### Ingestion Failures

Check orchestrator logs for:
```
✓ Knowledge Graph ingestion completed for project abc-123
```

If you see:
```
⚠ Knowledge Graph ingestion failed: <error>
```

Common causes:
- Neo4j not running
- Invalid project path
- Python syntax errors in generated code

### Query Timeouts

If queries are slow:
- Check Neo4j indexes: `CREATE INDEX ON :Function(name)`
- Reduce `max_depth` parameter
- Use more specific patterns

## Summary

The Knowledge Graph is now a **first-class citizen** in the agent workflow:

✅ **Automatic ingestion** after code generation  
✅ **Tools available** to all agents  
✅ **Impact analysis** in Reflexion Engine  
✅ **Semantic queries** for context-aware decisions  

The loop is closed! Agents can now "see" the codebase structure and make informed decisions.
