# Knowledge Graph Quick Start Guide

## 5-Minute Setup

### 1. Start Neo4j

```bash
docker-compose up -d neo4j
```

Verify it's running:
```bash
docker-compose ps neo4j
```

Access Neo4j Browser: http://localhost:7474
- Username: `neo4j`
- Password: `neo4j_password`

### 2. Run the Demo

```bash
python examples/knowledge_graph_demo.py
```

This demonstrates:
- Code parsing
- Graph operations
- Querying and analysis
- Project ingestion

### 3. Run Tests

```bash
pytest tests/test_knowledge_graph.py -v
pytest tests/test_code_parser.py -v
```

## Common Use Cases

### Parse a Python File

```python
from foundry.graph.code_parser import python_parser

module = python_parser.parse_file("path/to/file.py")

print(f"Functions: {len(module.functions)}")
print(f"Classes: {len(module.classes)}")
print(f"Imports: {len(module.imports)}")
```

### Ingest a Project

```python
from foundry.services.knowledge_graph import knowledge_graph_service
from foundry.graph.ingestion import ingestion_pipeline

# Initialize
await knowledge_graph_service.initialize()

# Ingest
stats = await ingestion_pipeline.ingest_project(
    project_id="my-project",
    project_name="My Project",
    project_path="/path/to/project"
)

print(f"Processed {stats['files_processed']} files")
print(f"Created {stats['functions_created']} functions")
```

### Query Dependencies

```python
# Find what a component depends on
deps = await knowledge_graph_service.find_dependencies(
    component_id="comp-123",
    depth=2
)

for dep in deps:
    print(f"{dep['name']} at distance {dep['distance']}")
```

### Analyze Impact

```python
# Find what depends on a component
impact = await knowledge_graph_service.analyze_impact(
    component_id="comp-123"
)

print(f"Affected components: {len(impact['affected_components'])}")
for affected in impact['affected_components']:
    print(f"  {affected['name']} (distance: {affected['distance']})")
```

### Search for Code

```python
# Search by function name
results = await knowledge_graph_service.search_patterns(
    pattern_type="function_name",
    pattern_value="authenticate",
    project_id="my-project"
)

for result in results:
    print(f"{result['name']} in {result['file_path']}")
```

### Get Context for Agents

```python
# Get relevant context for AI agents
context = await knowledge_graph_service.get_project_context(
    project_id="my-project",
    focus_components=["auth_module", "user_module"],
    include_dependencies=True
)

# Use in agent prompt
prompt = f"""
Components: {context['components']}
Dependencies: {context['dependencies']}

Task: Implement new feature...
"""
```

## Integration with Project Service

The Knowledge Graph is automatically integrated:

```python
from foundry.services.project_service import project_service

# Create project (graph is initialized automatically)
project = await project_service.create_project(
    session=db_session,
    name="My Project",
    requirements="Build a web app"
)

# Ingest code into graph
stats = await project_service.ingest_project_to_graph(project)

# Delete project (graph is cleaned up automatically)
await project_service.delete_project(
    session=db_session,
    project_id=project.id,
    confirmed=True
)
```

## Cypher Queries (Advanced)

Access Neo4j directly for custom queries:

```python
from foundry.graph.neo4j_client import neo4j_client

# Find all functions with high complexity
query = """
MATCH (f:Function)
WHERE f.complexity > 10
RETURN f.name, f.complexity, f.file_path
ORDER BY f.complexity DESC
LIMIT 10
"""

results = await neo4j_client.execute_query(query)
```

## Troubleshooting

### Can't connect to Neo4j

```bash
# Check if running
docker-compose ps neo4j

# Check logs
docker-compose logs neo4j

# Restart
docker-compose restart neo4j
```

### Slow queries

```python
# Limit depth
deps = await knowledge_graph_service.find_dependencies(
    component_id="comp-123",
    depth=1  # Instead of 3
)

# Focus on specific components
context = await knowledge_graph_service.get_project_context(
    project_id="my-project",
    focus_components=["comp-123"],  # Specific components only
    include_dependencies=False  # Skip if not needed
)
```

### Clear all data

```python
# Clear specific project
await knowledge_graph_service.clear_project("project-id")

# Or use Cypher to clear everything
query = "MATCH (n) DETACH DELETE n"
await neo4j_client.execute_write(query)
```

## Next Steps

1. Read full documentation: `docs/KNOWLEDGE_GRAPH.md`
2. Explore the demo: `examples/knowledge_graph_demo.py`
3. Check test examples: `tests/test_knowledge_graph.py`
4. Integrate with your agents

## API Reference

### KnowledgeGraphService

- `initialize()` - Initialize with constraints/indexes
- `create_project()` - Create project node
- `store_component()` - Store code component
- `store_function()` - Store function node
- `store_class()` - Store class node
- `create_dependency()` - Create dependency relationship
- `create_call_relationship()` - Create function call
- `find_dependencies()` - Query dependencies
- `analyze_impact()` - Impact analysis
- `search_patterns()` - Pattern search
- `get_project_context()` - Get context for agents
- `clear_project()` - Delete project data

### PythonCodeParser

- `parse_file()` - Parse single file
- `parse_directory()` - Parse directory
- `build_dependency_graph()` - Build dependency graph

### IngestionPipeline

- `ingest_project()` - Ingest entire project
- `ingest_file()` - Ingest single file
- `handle_file_deletion()` - Handle deletion
- `refresh_project()` - Refresh project data

## Configuration

Environment variables (`.env`):

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_password
```

## Support

- Documentation: `docs/KNOWLEDGE_GRAPH.md`
- Status: `docs/NEO4J_INTEGRATION_STATUS.md`
- Issues: Check logs and Neo4j Browser
