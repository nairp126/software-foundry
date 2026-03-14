"""Tests for Knowledge Graph service."""

import pytest
from uuid import uuid4

from foundry.services.knowledge_graph import KnowledgeGraphService
from foundry.graph.neo4j_client import Neo4jClient


@pytest.fixture
async def kg_service():
    """Create a Knowledge Graph service for testing."""
    service = KnowledgeGraphService()
    await service.initialize()
    yield service
    await service.disconnect()


@pytest.fixture
def test_project_id():
    """Generate a unique project ID for testing."""
    return f"test_project_{uuid4()}"


@pytest.fixture
def test_component_id():
    """Generate a unique component ID for testing."""
    return f"test_component_{uuid4()}"


@pytest.mark.asyncio
class TestKnowledgeGraphConnection:
    """Test Neo4j connection and health checks."""
    
    async def test_connection(self, kg_service):
        """Test that we can connect to Neo4j."""
        health = await kg_service.client.health_check()
        assert health is True
    
    async def test_create_constraints(self, kg_service):
        """Test that constraints are created successfully."""
        # This is called during initialize, so just verify it doesn't error
        await kg_service.client.create_constraints()


@pytest.mark.asyncio
class TestProjectOperations:
    """Test project-level operations."""
    
    async def test_create_project(self, kg_service, test_project_id):
        """Test creating a project node."""
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={"description": "A test project"}
        )
        
        # Verify project was created
        query = "MATCH (p:Project {id: $project_id}) RETURN p"
        result = await kg_service.client.execute_query(
            query,
            {"project_id": test_project_id}
        )
        
        assert len(result) == 1
        assert result[0]["p"]["name"] == "Test Project"
        
        # Cleanup
        await kg_service.clear_project(test_project_id)
    
    async def test_clear_project(self, kg_service, test_project_id):
        """Test clearing a project."""
        # Create a project
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        # Clear it
        await kg_service.clear_project(test_project_id)
        
        # Verify it's gone
        query = "MATCH (p:Project {id: $project_id}) RETURN p"
        result = await kg_service.client.execute_query(
            query,
            {"project_id": test_project_id}
        )
        
        assert len(result) == 0


@pytest.mark.asyncio
class TestComponentOperations:
    """Test component-level operations."""
    
    async def test_store_component(self, kg_service, test_project_id, test_component_id):
        """Test storing a component."""
        # Create project first
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        # Store component
        await kg_service.store_component(
            project_id=test_project_id,
            component_id=test_component_id,
            name="test_module",
            component_type="module",
            file_path="/test/module.py",
            metadata={"lines": 100}
        )
        
        # Verify component was created
        query = "MATCH (c:Component {id: $component_id}) RETURN c"
        result = await kg_service.client.execute_query(
            query,
            {"component_id": test_component_id}
        )
        
        assert len(result) == 1
        assert result[0]["c"]["name"] == "test_module"
        assert result[0]["c"]["type"] == "module"
        
        # Cleanup
        await kg_service.clear_project(test_project_id)
    
    async def test_delete_component(self, kg_service, test_project_id, test_component_id):
        """Test deleting a component."""
        # Create project and component
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        await kg_service.store_component(
            project_id=test_project_id,
            component_id=test_component_id,
            name="test_module",
            component_type="module",
            file_path="/test/module.py",
            metadata={}
        )
        
        # Delete component
        await kg_service.delete_component(test_component_id)
        
        # Verify it's gone
        query = "MATCH (c:Component {id: $component_id}) RETURN c"
        result = await kg_service.client.execute_query(
            query,
            {"component_id": test_component_id}
        )
        
        assert len(result) == 0
        
        # Cleanup
        await kg_service.clear_project(test_project_id)


@pytest.mark.asyncio
class TestFunctionOperations:
    """Test function-level operations."""
    
    async def test_store_function(self, kg_service, test_project_id):
        """Test storing a function."""
        # Create project
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        function_id = f"test_function_{uuid4()}"
        
        # Store function
        await kg_service.store_function(
            project_id=test_project_id,
            function_id=function_id,
            name="test_func",
            signature="test_func(x: int) -> str",
            file_path="/test/module.py",
            line_number=10,
            complexity=3
        )
        
        # Verify function was created
        query = "MATCH (f:Function {id: $function_id}) RETURN f"
        result = await kg_service.client.execute_query(
            query,
            {"function_id": function_id}
        )
        
        assert len(result) == 1
        assert result[0]["f"]["name"] == "test_func"
        assert result[0]["f"]["complexity"] == 3
        
        # Cleanup
        await kg_service.clear_project(test_project_id)


@pytest.mark.asyncio
class TestClassOperations:
    """Test class-level operations."""
    
    async def test_store_class(self, kg_service, test_project_id):
        """Test storing a class."""
        # Create project
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        class_id = f"test_class_{uuid4()}"
        
        # Store class
        await kg_service.store_class(
            project_id=test_project_id,
            class_id=class_id,
            name="TestClass",
            file_path="/test/module.py",
            line_number=20,
            methods=["method1", "method2"],
            base_classes=["BaseClass"]
        )
        
        # Verify class was created
        query = "MATCH (c:Class {id: $class_id}) RETURN c"
        result = await kg_service.client.execute_query(
            query,
            {"class_id": class_id}
        )
        
        assert len(result) == 1
        assert result[0]["c"]["name"] == "TestClass"
        assert result[0]["c"]["methods"] == ["method1", "method2"]
        
        # Cleanup
        await kg_service.clear_project(test_project_id)


@pytest.mark.asyncio
class TestRelationships:
    """Test relationship operations."""
    
    async def test_create_dependency(self, kg_service, test_project_id):
        """Test creating a dependency relationship."""
        # Create project
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        # Create two components
        comp1_id = f"comp1_{uuid4()}"
        comp2_id = f"comp2_{uuid4()}"
        
        await kg_service.store_component(
            project_id=test_project_id,
            component_id=comp1_id,
            name="component1",
            component_type="module",
            file_path="/test/comp1.py",
            metadata={}
        )
        
        await kg_service.store_component(
            project_id=test_project_id,
            component_id=comp2_id,
            name="component2",
            component_type="module",
            file_path="/test/comp2.py",
            metadata={}
        )
        
        # Create dependency
        await kg_service.create_dependency(
            from_component_id=comp1_id,
            to_component_id=comp2_id,
            dependency_type="imports"
        )
        
        # Verify relationship
        query = """
        MATCH (from:Component {id: $from_id})-[r:DEPENDS_ON]->(to:Component {id: $to_id})
        RETURN r
        """
        result = await kg_service.client.execute_query(
            query,
            {"from_id": comp1_id, "to_id": comp2_id}
        )
        
        assert len(result) == 1
        
        # Cleanup
        await kg_service.clear_project(test_project_id)
    
    async def test_create_call_relationship(self, kg_service, test_project_id):
        """Test creating a function call relationship."""
        # Create project
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        # Create two functions
        func1_id = f"func1_{uuid4()}"
        func2_id = f"func2_{uuid4()}"
        
        await kg_service.store_function(
            project_id=test_project_id,
            function_id=func1_id,
            name="caller",
            signature="caller()",
            file_path="/test/module.py",
            line_number=10,
            complexity=1
        )
        
        await kg_service.store_function(
            project_id=test_project_id,
            function_id=func2_id,
            name="callee",
            signature="callee()",
            file_path="/test/module.py",
            line_number=20,
            complexity=1
        )
        
        # Create call relationship
        await kg_service.create_call_relationship(
            caller_function_id=func1_id,
            callee_function_id=func2_id,
            call_count=3
        )
        
        # Verify relationship
        query = """
        MATCH (caller:Function {id: $caller_id})-[r:CALLS]->(callee:Function {id: $callee_id})
        RETURN r.count as count
        """
        result = await kg_service.client.execute_query(
            query,
            {"caller_id": func1_id, "callee_id": func2_id}
        )
        
        assert len(result) == 1
        assert result[0]["count"] == 3
        
        # Cleanup
        await kg_service.clear_project(test_project_id)


@pytest.mark.asyncio
class TestQueries:
    """Test query operations."""
    
    async def test_find_dependencies(self, kg_service, test_project_id):
        """Test finding dependencies of a component."""
        # Create project
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        # Create a chain of dependencies: A -> B -> C
        comp_a = f"comp_a_{uuid4()}"
        comp_b = f"comp_b_{uuid4()}"
        comp_c = f"comp_c_{uuid4()}"
        
        for comp_id, name in [(comp_a, "A"), (comp_b, "B"), (comp_c, "C")]:
            await kg_service.store_component(
                project_id=test_project_id,
                component_id=comp_id,
                name=name,
                component_type="module",
                file_path=f"/test/{name}.py",
                metadata={}
            )
        
        await kg_service.create_dependency(comp_a, comp_b)
        await kg_service.create_dependency(comp_b, comp_c)
        
        # Find dependencies of A
        deps = await kg_service.find_dependencies(comp_a, depth=2)
        
        assert len(deps) >= 1  # Should find at least B
        dep_names = [d["name"] for d in deps]
        assert "B" in dep_names
        
        # Cleanup
        await kg_service.clear_project(test_project_id)
    
    async def test_analyze_impact(self, kg_service, test_project_id):
        """Test impact analysis."""
        # Create project
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        # Create dependencies: A -> B, C -> B (B is depended on by A and C)
        comp_a = f"comp_a_{uuid4()}"
        comp_b = f"comp_b_{uuid4()}"
        comp_c = f"comp_c_{uuid4()}"
        
        for comp_id, name in [(comp_a, "A"), (comp_b, "B"), (comp_c, "C")]:
            await kg_service.store_component(
                project_id=test_project_id,
                component_id=comp_id,
                name=name,
                component_type="module",
                file_path=f"/test/{name}.py",
                metadata={}
            )
        
        await kg_service.create_dependency(comp_a, comp_b)
        await kg_service.create_dependency(comp_c, comp_b)
        
        # Analyze impact of changing B
        impact = await kg_service.analyze_impact(comp_b)
        
        assert "affected_components" in impact
        affected_names = [c["name"] for c in impact["affected_components"]]
        assert "A" in affected_names
        assert "C" in affected_names
        
        # Cleanup
        await kg_service.clear_project(test_project_id)
    
    async def test_search_patterns(self, kg_service, test_project_id):
        """Test pattern search."""
        # Create project
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        # Create some functions
        for i in range(3):
            func_id = f"func_{i}_{uuid4()}"
            await kg_service.store_function(
                project_id=test_project_id,
                function_id=func_id,
                name=f"test_function_{i}",
                signature=f"test_function_{i}()",
                file_path="/test/module.py",
                line_number=10 + i * 10,
                complexity=1
            )
        
        # Search for functions with "test" in the name
        results = await kg_service.search_patterns(
            pattern_type="function_name",
            pattern_value="test_function",
            project_id=test_project_id
        )
        
        assert len(results) >= 3
        
        # Cleanup
        await kg_service.clear_project(test_project_id)
    
    async def test_get_project_context(self, kg_service, test_project_id):
        """Test getting project context."""
        # Create project
        await kg_service.create_project(
            project_id=test_project_id,
            name="Test Project",
            metadata={}
        )
        
        # Create some components
        comp_ids = []
        for i in range(2):
            comp_id = f"comp_{i}_{uuid4()}"
            comp_ids.append(comp_id)
            await kg_service.store_component(
                project_id=test_project_id,
                component_id=comp_id,
                name=f"component_{i}",
                component_type="module",
                file_path=f"/test/comp{i}.py",
                metadata={}
            )
        
        # Get project context
        context = await kg_service.get_project_context(test_project_id)
        
        assert "components" in context
        assert len(context["components"]) >= 2
        
        # Cleanup
        await kg_service.clear_project(test_project_id)
