# Knowledge Graph Integration

## Overview

The Knowledge Graph is a core component of the Autonomous Software Foundry that provides semantic understanding of code structure, relationships, and dependencies. It uses Neo4j as the graph database to store and query code components, enabling intelligent context retrieval for AI agents.

## Architecture

### Components

1. **Neo4j Client** (`src/foundry/graph/neo4j_client.py`)
   - Manages connections to Neo4j database
   - Provides async query execution
   - Handles constraints and indexes

2. **Knowledge Graph Service** (`src/foundry/services/knowledge_graph.py`)
   - High-level API for graph operations
   - CRUD operations for nodes and relationships
   - Query methods for dependencies and impact analysis

3. **Code Parser** (`src/foundry/graph/code_parser.py`)
   - Parses Python code using AST
   - Extracts functions, classes, imports
   - Calculates complexity metrics
   - Identifies function calls and dependencies

4. **Ingestion Pipeline** (`src/foundry/graph/ingestion.py`)
   - Ingests entire projects into the graph
   - Handles incremental updates
   - Manages file deletions
   - Builds dependency relationships

### Graph Schema

#### Node Types

- **Project**: Represents a software project
  - Properties: `id`, `name`, `created_at`, `metadata`

- **Component**: Represents a code module/file
  - Properties: `id`, `name`, `type`, `file_path`, `metadata`, `created_at`

- **Function**: Represents a function or method
  - Properties: `id`, `name`, `signature`, `file_path`, `line_number`, `complexity`, `created_at`

- **Class**: Represents a class definition
  - Properties: `id`, `name`, `file_path`, `line_number`, `methods`, `base_classes`, `created_at`

- **Module**: Represents a Python module
  - Properties: `id`, `file_path`, `imports`, `exports`, `created_at`

#### Relationship Types

- **CONTAINS**: Project contains Components, Functions, Classes
- **DEPENDS_ON**: Component depends on another Component
- **CALLS**: Function calls another Function
- **DEFINES**: Component defines Functions or Classes
- **IMPORTS**: Module imports another Module
- **INHERITS_FROM**: Class inherits from another Class (future)

## Usage

### Initialization

```python
from foundry.services.knowledge_graph import knowledge_graph_service

# Initialize the Knowledge Graph (creates constraints and indexes)
await knowledge_graph_service.initialize()
```

### Creating a Project

```python
await knowledge_graph_service.create_project(
    project_id="my-project-123",
    name="My Project",
    metadata={"description": "A sample project"}
)
```

### Storing Components

```python
# Store a component (module/file)
await knowledge_graph_service.store_component(
    project_id="my-project-123",
    component_id="comp-456",
    name="auth_module",
    component_type="module",
    file_path="/src/auth.py",
    metadata={"lines": 150}
)

# Store a function
await knowledge_graph_service.store_function(
    project_id="my-project-123",
    function_id="func-789",
    name="authenticate",
    signature="authenticate(username: str, password: str) -> bool",
    file_path="/src/auth.py",
    line_number=10,
    complexity=5,
    parent_component_id="comp-456"
)

# Store a class
await knowledge_graph_service.store_class(
    project_id="my-project-123",
    class_id="class-101",
    name="User",
    file_path="/src/models.py",
    line_number=20,
    methods=["__init__", "validate", "save"],
    base_classes=["BaseModel"]
)
```

### Creating Relationships

```python
# Create a dependency between components
await knowledge_graph_service.create_dependency(
    from_component_id="comp-456",
    to_component_id="comp-789",
    dependency_type="imports"
)

# Create a function call relationship
await knowledge_graph_service.create_call_relationship(
    caller_function_id="func-123",
    callee_function_id="func-456",
    call_count=3
)
```

### Querying the Graph

```python
# Find dependencies of a component
deps = await knowledge_graph_service.find_dependencies(
    component_id="comp-456",
    depth=2  # How many levels deep to search
)

# Analyze impact of changes
impact = await knowledge_graph_service.analyze_impact(
    component_id="comp-456",
    max_depth=3
)
print(f"Affected components: {len(impact['affected_components'])}")

# Search for patterns
results = await knowledge_graph_service.search_patterns(
    pattern_type="function_name",
    pattern_value="auth",
    project_id="my-project-123"
)

# Get project context for agents
context = await knowledge_graph_service.get_project_context(
    project_id="my-project-123",
    focus_components=["comp-456", "comp-789"],
    include_dependencies=True
)
```

### Ingesting Projects

```python
from foundry.graph.ingestion import ingestion_pipeline

# Ingest an entire project
stats = await ingestion_pipeline.ingest_project(
    project_id="my-project-123",
    project_name="My Project",
    project_path="/path/to/project",
    metadata={"version": "1.0.0"}
)

print(f"Files processed: {stats['files_processed']}")
print(f"Functions created: {stats['functions_created']}")
print(f"Classes created: {stats['classes_created']}")

# Ingest a single file
stats = await ingestion_pipeline.ingest_file(
    project_id="my-project-123",
    file_path="/path/to/file.py",
    update_existing=True
)

# Handle file deletion
success = await ingestion_pipeline.handle_file_deletion(
    project_id="my-project-123",
    file_path="/path/to/deleted_file.py"
)
```

### Code Parsing

```python
from foundry.graph.code_parser import python_parser

# Parse a single file
module = python_parser.parse_file("/path/to/file.py")

print(f"Functions: {len(module.functions)}")
for func in module.functions:
    print(f"  {func.name}: complexity={func.complexity}")

print(f"Classes: {len(module.classes)}")
for cls in module.classes:
    print(f"  {cls.name}: methods={cls.methods}")

# Parse a directory
parsed_modules = python_parser.parse_directory(
    "/path/to/project",
    exclude_patterns=["venv", "node_modules"]
)

# Build dependency graph
dep_graph = python_parser.build_dependency_graph(parsed_modules)
```

## Integration with Project Service

The Knowledge Graph is automatically integrated with the Project Service:

```python
from foundry.services.project_service import project_service

# When creating a project, the Knowledge Graph is initialized
project = await project_service.create_project(
    session=db_session,
    name="My Project",
    requirements="Build a web app",
    description="A sample project"
)

# Ingest project code into the graph
stats = await project_service.ingest_project_to_graph(project)

# When deleting a project, the graph is cleaned up
result = await project_service.delete_project(
    session=db_session,
    project_id=project.id,
    confirmed=True
)
```

## Agent Integration

Agents can use the Knowledge Graph to get intelligent context:

```python
# Get relevant context for a task
context = await knowledge_graph_service.get_project_context(
    project_id=project_id,
    focus_components=["auth_module", "user_module"],
    include_dependencies=True
)

# Use context in agent prompt
prompt = f"""
You are working on a project with the following components:
{context['components']}

Dependencies:
{context['dependencies']}

Task: Implement authentication feature
"""
```

## Performance Considerations

### Indexes

The following indexes are automatically created:
- Unique constraints on `id` for all node types
- Indexes on `name` for Projects, Components, Functions, Classes
- Index on `file_path` for Modules

### Query Optimization

- Use `depth` parameter to limit traversal depth
- Use `focus_components` to narrow context retrieval
- Batch operations when ingesting large projects

### Caching

Consider caching frequently accessed data:
- Project context for active projects
- Dependency graphs for critical components
- Search results for common patterns

## Testing

Run the Knowledge Graph tests:

```bash
# Run all Knowledge Graph tests
pytest tests/test_knowledge_graph.py -v

# Run code parser tests
pytest tests/test_code_parser.py -v

# Run with Neo4j container
docker-compose up -d neo4j
pytest tests/test_knowledge_graph.py -v
```

## Demo

Run the demo script to see the Knowledge Graph in action:

```bash
python examples/knowledge_graph_demo.py
```

The demo shows:
1. Code parsing capabilities
2. Graph operations (CRUD)
3. Querying and analysis
4. Project ingestion

## Configuration

Neo4j connection settings in `.env`:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_password
```

## Troubleshooting

### Connection Issues

If you can't connect to Neo4j:

1. Check if Neo4j is running:
   ```bash
   docker-compose ps neo4j
   ```

2. Check logs:
   ```bash
   docker-compose logs neo4j
   ```

3. Verify credentials in `.env` match `docker-compose.yml`

### Performance Issues

If queries are slow:

1. Check if indexes are created:
   ```cypher
   SHOW INDEXES
   ```

2. Use `EXPLAIN` to analyze queries:
   ```cypher
   EXPLAIN MATCH (p:Project)-[:CONTAINS]->(c:Component) RETURN c
   ```

3. Limit query depth and result size

### Data Inconsistency

If data seems inconsistent:

1. Clear and re-ingest the project:
   ```python
   await knowledge_graph_service.clear_project(project_id)
   await ingestion_pipeline.ingest_project(...)
   ```

2. Check for parsing errors in logs

## Future Enhancements

1. **Multi-language Support**
   - JavaScript/TypeScript parser
   - Java parser
   - Go parser

2. **Advanced Analysis**
   - Code smell detection
   - Circular dependency detection
   - Dead code identification

3. **Semantic Search**
   - Vector embeddings for code
   - Similarity search
   - Natural language queries

4. **Real-time Updates**
   - File watcher integration
   - Incremental updates
   - Change notifications

5. **Visualization**
   - Dependency graphs
   - Call graphs
   - Architecture diagrams

## References

- [Neo4j Python Driver Documentation](https://neo4j.com/docs/python-manual/current/)
- [Python AST Documentation](https://docs.python.org/3/library/ast.html)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/current/)
