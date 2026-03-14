"""Demo script for Knowledge Graph integration.

This script demonstrates how to use the Knowledge Graph to:
1. Parse Python code and extract structure
2. Store code components in Neo4j
3. Query dependencies and relationships
4. Perform impact analysis
5. Search for code patterns
"""

import asyncio
import tempfile
from pathlib import Path
from uuid import uuid4

from foundry.graph.code_parser import python_parser
from foundry.services.knowledge_graph import knowledge_graph_service
from foundry.graph.ingestion import ingestion_pipeline


async def demo_code_parsing():
    """Demonstrate code parsing capabilities."""
    print("\n=== Code Parsing Demo ===\n")
    
    # Create a sample Python file
    sample_code = '''"""Sample module for demonstration."""

import os
from typing import List

class DataProcessor:
    """Process data efficiently."""
    
    def __init__(self, name: str):
        self.name = name
    
    def process(self, data: List[int]) -> List[int]:
        """Process the data."""
        return [x * 2 for x in data]
    
    def save(self, filename: str):
        """Save results to file."""
        with open(filename, 'w') as f:
            f.write(self.name)


def helper_function(x: int, y: int) -> int:
    """Helper function with some complexity."""
    if x > y:
        return x
    elif x < y:
        return y
    else:
        return 0


async def async_operation(data: str) -> str:
    """Async operation example."""
    return data.upper()
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(sample_code)
        temp_file = f.name
    
    try:
        # Parse the file
        module = python_parser.parse_file(temp_file)
        
        print(f"File: {module.file_path}")
        print(f"Docstring: {module.docstring}")
        print(f"\nFunctions found: {len(module.functions)}")
        for func in module.functions:
            print(f"  - {func.name}: {func.signature}")
            print(f"    Lines: {func.line_number}-{func.end_line}")
            print(f"    Complexity: {func.complexity}")
            print(f"    Async: {func.is_async}")
        
        print(f"\nClasses found: {len(module.classes)}")
        for cls in module.classes:
            print(f"  - {cls.name}")
            print(f"    Methods: {', '.join(cls.methods)}")
            print(f"    Base classes: {', '.join(cls.base_classes) if cls.base_classes else 'None'}")
        
        print(f"\nImports found: {len(module.imports)}")
        for imp in module.imports:
            print(f"  - {imp.module}")
    
    finally:
        Path(temp_file).unlink()


async def demo_knowledge_graph():
    """Demonstrate Knowledge Graph operations."""
    print("\n=== Knowledge Graph Demo ===\n")
    
    # Initialize the Knowledge Graph
    await knowledge_graph_service.initialize()
    
    # Create a test project
    project_id = f"demo_project_{uuid4()}"
    print(f"Creating project: {project_id}")
    
    await knowledge_graph_service.create_project(
        project_id=project_id,
        name="Demo Project",
        metadata={"description": "A demo project"}
    )
    
    # Create some components
    comp1_id = f"comp1_{uuid4()}"
    comp2_id = f"comp2_{uuid4()}"
    
    print("\nCreating components...")
    await knowledge_graph_service.store_component(
        project_id=project_id,
        component_id=comp1_id,
        name="auth_module",
        component_type="module",
        file_path="/src/auth.py",
        metadata={"lines": 150}
    )
    
    await knowledge_graph_service.store_component(
        project_id=project_id,
        component_id=comp2_id,
        name="user_module",
        component_type="module",
        file_path="/src/user.py",
        metadata={"lines": 200}
    )
    
    # Create a dependency
    print("Creating dependency: user_module -> auth_module")
    await knowledge_graph_service.create_dependency(
        from_component_id=comp2_id,
        to_component_id=comp1_id,
        dependency_type="imports"
    )
    
    # Create some functions
    func1_id = f"func1_{uuid4()}"
    func2_id = f"func2_{uuid4()}"
    
    print("\nCreating functions...")
    await knowledge_graph_service.store_function(
        project_id=project_id,
        function_id=func1_id,
        name="authenticate",
        signature="authenticate(username: str, password: str) -> bool",
        file_path="/src/auth.py",
        line_number=10,
        complexity=5,
        parent_component_id=comp1_id
    )
    
    await knowledge_graph_service.store_function(
        project_id=project_id,
        function_id=func2_id,
        name="create_user",
        signature="create_user(username: str) -> User",
        file_path="/src/user.py",
        line_number=20,
        complexity=3,
        parent_component_id=comp2_id
    )
    
    # Create a call relationship
    print("Creating call relationship: create_user -> authenticate")
    await knowledge_graph_service.create_call_relationship(
        caller_function_id=func2_id,
        callee_function_id=func1_id,
        call_count=1
    )
    
    # Query dependencies
    print("\n--- Querying Dependencies ---")
    deps = await knowledge_graph_service.find_dependencies(comp2_id, depth=1)
    print(f"Dependencies of user_module: {len(deps)}")
    for dep in deps:
        print(f"  - {dep['name']} ({dep['type']})")
    
    # Analyze impact
    print("\n--- Impact Analysis ---")
    impact = await knowledge_graph_service.analyze_impact(comp1_id)
    print(f"Impact of changing auth_module:")
    print(f"  Affected components: {len(impact.get('affected_components', []))}")
    for affected in impact.get('affected_components', []):
        print(f"    - {affected['name']} (distance: {affected['distance']})")
    
    # Search patterns
    print("\n--- Pattern Search ---")
    results = await knowledge_graph_service.search_patterns(
        pattern_type="function_name",
        pattern_value="auth",
        project_id=project_id
    )
    print(f"Functions matching 'auth': {len(results)}")
    for result in results:
        print(f"  - {result['name']} in {result['file_path']}")
    
    # Get project context
    print("\n--- Project Context ---")
    context = await knowledge_graph_service.get_project_context(project_id)
    print(f"Components: {len(context['components'])}")
    print(f"Dependencies: {len(context['dependencies'])}")
    
    # Cleanup
    print("\n--- Cleanup ---")
    await knowledge_graph_service.clear_project(project_id)
    print("Project cleared from graph")


async def demo_ingestion():
    """Demonstrate ingesting a real project."""
    print("\n=== Project Ingestion Demo ===\n")
    
    # Create a temporary project structure
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create some Python files
        src_dir = Path(temp_dir) / "src"
        src_dir.mkdir()
        
        # File 1: models.py
        models_file = src_dir / "models.py"
        models_file.write_text('''"""Data models."""

class User:
    """User model."""
    
    def __init__(self, username: str):
        self.username = username
    
    def validate(self) -> bool:
        """Validate user data."""
        return len(self.username) > 0


class Post:
    """Post model."""
    
    def __init__(self, title: str, author: User):
        self.title = title
        self.author = author
''')
        
        # File 2: service.py
        service_file = src_dir / "service.py"
        service_file.write_text('''"""Business logic."""

from models import User, Post


def create_user(username: str) -> User:
    """Create a new user."""
    user = User(username)
    if user.validate():
        return user
    raise ValueError("Invalid user")


def create_post(title: str, user: User) -> Post:
    """Create a new post."""
    return Post(title, user)
''')
        
        # Initialize Knowledge Graph
        await knowledge_graph_service.initialize()
        
        # Ingest the project
        project_id = f"ingestion_demo_{uuid4()}"
        print(f"Ingesting project: {project_id}")
        print(f"Project path: {temp_dir}")
        
        stats = await ingestion_pipeline.ingest_project(
            project_id=project_id,
            project_name="Ingestion Demo",
            project_path=temp_dir,
            metadata={"demo": True}
        )
        
        print("\n--- Ingestion Statistics ---")
        print(f"Files processed: {stats['files_processed']}")
        print(f"Functions created: {stats['functions_created']}")
        print(f"Classes created: {stats['classes_created']}")
        print(f"Modules created: {stats['modules_created']}")
        print(f"Dependencies created: {stats['dependencies_created']}")
        
        if stats['errors']:
            print(f"\nErrors: {len(stats['errors'])}")
            for error in stats['errors']:
                print(f"  - {error}")
        
        # Query the ingested data
        print("\n--- Querying Ingested Data ---")
        context = await knowledge_graph_service.get_project_context(project_id)
        print(f"Total components: {len(context['components'])}")
        for comp in context['components']:
            print(f"  - {comp['name']} ({comp['type']})")
        
        # Search for classes
        classes = await knowledge_graph_service.search_patterns(
            pattern_type="class_name",
            pattern_value="User",
            project_id=project_id
        )
        print(f"\nClasses found: {len(classes)}")
        for cls in classes:
            print(f"  - {cls['name']} at line {cls['line_number']}")
        
        # Cleanup
        print("\n--- Cleanup ---")
        await knowledge_graph_service.clear_project(project_id)
        print("Project cleared from graph")


async def main():
    """Run all demos."""
    print("=" * 60)
    print("Knowledge Graph Integration Demo")
    print("=" * 60)
    
    try:
        # Demo 1: Code Parsing
        await demo_code_parsing()
        
        # Demo 2: Knowledge Graph Operations
        await demo_knowledge_graph()
        
        # Demo 3: Project Ingestion
        await demo_ingestion()
        
        print("\n" + "=" * 60)
        print("All demos completed successfully!")
        print("=" * 60)
    
    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Properly close Neo4j connection
        from foundry.graph.neo4j_client import neo4j_client
        await neo4j_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
