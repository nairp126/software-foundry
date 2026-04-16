"""Knowledge Graph service for semantic code understanding."""

import logging
import json
from typing import Dict, Any, List, Optional
from uuid import uuid4

from foundry.graph.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """Service for managing the Knowledge Graph."""

    def __init__(self):
        """Initialize Knowledge Graph service."""
        self.client = neo4j_client

    async def initialize(self) -> None:
        """Initialize the Knowledge Graph with constraints and indexes."""
        await self.client.connect()
        await self.client.create_constraints()
        logger.info("Knowledge Graph initialized")

    async def disconnect(self) -> None:
        """Disconnect from the Knowledge Graph."""
        await self.client.disconnect()
        logger.info("Knowledge Graph disconnected")

    async def create_project(self, project_id: str, name: str, metadata: Dict[str, Any]) -> None:
        """Create a project node in the graph."""
        query = """
        CREATE (p:Project {
            id: $project_id,
            name: $name,
            created_at: datetime(),
            metadata: $metadata
        })
        RETURN p
        """
        await self.client.execute_write(
            query,
            {
                "project_id": project_id,
                "name": name,
                "metadata": json.dumps(metadata) if metadata else "{}",
            }
        )
        logger.info(f"Created project node: {project_id}")

    async def store_component(
        self,
        project_id: str,
        component_id: str,
        name: str,
        component_type: str,
        file_path: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Store a code component in the graph."""
        query = """
        MATCH (p:Project {id: $project_id})
        CREATE (c:Component {
            id: $component_id,
            name: $name,
            type: $component_type,
            file_path: $file_path,
            metadata: $metadata,
            created_at: datetime()
        })
        CREATE (p)-[:CONTAINS]->(c)
        RETURN c
        """
        await self.client.execute_write(
            query,
            {
                "project_id": project_id,
                "component_id": component_id,
                "name": name,
                "component_type": component_type,
                "file_path": file_path,
                "metadata": json.dumps(metadata) if metadata else "{}",
            }
        )

    async def store_function(
        self,
        project_id: str,
        function_id: str,
        name: str,
        signature: str,
        file_path: str,
        line_number: int,
        complexity: int,
        parent_component_id: Optional[str] = None,
        content: Optional[str] = None,
    ) -> None:
        """Store a function node in the graph."""
        query = """
        MATCH (p:Project {id: $project_id})
        CREATE (f:Function {
            id: $function_id,
            name: $name,
            signature: $signature,
            file_path: $file_path,
            line_number: $line_number,
            complexity: $complexity,
            content: $content,
            created_at: datetime()
        })
        CREATE (p)-[:CONTAINS]->(f)
        """
        
        if parent_component_id:
            query += """
            WITH f
            MATCH (c:Component {id: $parent_component_id})
            CREATE (c)-[:DEFINES]->(f)
            """
        
        query += " RETURN f"
        
        await self.client.execute_write(
            query,
            {
                "project_id": project_id,
                "function_id": function_id,
                "name": name,
                "signature": signature,
                "file_path": file_path,
                "line_number": line_number,
                "complexity": complexity,
                "content": content or "",
                "parent_component_id": parent_component_id,
            }
        )

    async def store_class(
        self,
        project_id: str,
        class_id: str,
        name: str,
        file_path: str,
        line_number: int,
        methods: List[str],
        base_classes: List[str],
        parent_component_id: Optional[str] = None,
        content: Optional[str] = None,
    ) -> None:
        """Store a class node in the graph."""
        query = """
        MATCH (p:Project {id: $project_id})
        CREATE (c:Class {
            id: $class_id,
            name: $name,
            file_path: $file_path,
            line_number: $line_number,
            methods: $methods,
            base_classes: $base_classes,
            content: $content,
            created_at: datetime()
        })
        CREATE (p)-[:CONTAINS]->(c)
        """
        
        if parent_component_id:
            query += """
            WITH c
            MATCH (comp:Component {id: $parent_component_id})
            CREATE (comp)-[:DEFINES]->(c)
            """
        
        query += " RETURN c"
        
        await self.client.execute_write(
            query,
            {
                "project_id": project_id,
                "class_id": class_id,
                "name": name,
                "file_path": file_path,
                "line_number": line_number,
                "methods": methods,
                "base_classes": base_classes,
                "content": content or "",
                "parent_component_id": parent_component_id,
            }
        )

    async def create_dependency(
        self,
        from_component_id: str,
        to_component_id: str,
        dependency_type: str = "DEPENDS_ON",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create a dependency relationship between components."""
        query = """
        MATCH (from:Component {id: $from_id})
        MATCH (to:Component {id: $to_id})
        CREATE (from)-[r:DEPENDS_ON {
            type: $dependency_type,
            metadata: $metadata,
            created_at: datetime()
        }]->(to)
        RETURN r
        """
        await self.client.execute_write(
            query,
            {
                "from_id": from_component_id,
                "to_id": to_component_id,
                "dependency_type": dependency_type,
                "metadata": json.dumps(metadata) if metadata else "{}",
            }
        )

    async def create_call_relationship(
        self,
        caller_function_id: str,
        callee_function_id: str,
        call_count: int = 1,
    ) -> None:
        """Create a CALLS relationship between functions."""
        query = """
        MATCH (caller:Function {id: $caller_id})
        MATCH (callee:Function {id: $callee_id})
        MERGE (caller)-[r:CALLS]->(callee)
        ON CREATE SET r.count = $call_count, r.created_at = datetime()
        ON MATCH SET r.count = r.count + $call_count
        RETURN r
        """
        await self.client.execute_write(
            query,
            {
                "caller_id": caller_function_id,
                "callee_id": callee_function_id,
                "call_count": call_count,
            }
        )

    async def find_dependencies(
        self,
        component_id: str,
        depth: int = 1,
    ) -> List[Dict[str, Any]]:
        """Find all dependencies of a component up to specified depth."""
        # Neo4j doesn't allow parameters in variable-length patterns
        # Use a reasonable max depth of 10
        max_depth = min(depth, 10)
        query = f"""
        MATCH path = (c:Component {{id: $component_id}})-[:DEPENDS_ON*1..{max_depth}]->(dep)
        RETURN dep.id as id, dep.name as name, dep.type as type, 
               dep.file_path as file_path, length(path) as distance
        ORDER BY distance
        """
        results = await self.client.execute_query(
            query,
            {"component_id": component_id}
        )
        return results

    async def analyze_impact(
        self,
        component_id: str,
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """Analyze the impact of changes to a component."""
        # Find components that depend on this one (reverse dependencies)
        # Neo4j doesn't allow parameters in variable-length patterns
        depth_limit = min(max_depth, 10)
        query = f"""
        MATCH (c:Component {{id: $component_id}})
        OPTIONAL MATCH path = (dependent:Component)-[:DEPENDS_ON*1..{depth_limit}]->(c)
        WHERE dependent IS NOT NULL
        WITH c.id as component_id, c.name as component_name,
             collect(DISTINCT {{
                id: dependent.id,
                name: dependent.name,
                type: dependent.type,
                file_path: dependent.file_path,
                distance: length(path)
            }}) as affected_components
        RETURN {{
            component_id: component_id,
            component_name: component_name,
            affected_components: affected_components
        }} as impact
        """
        results = await self.client.execute_query(
            query,
            {"component_id": component_id}
        )
        
        if results:
            return results[0].get("impact", {})
        return {"component_id": component_id, "affected_components": []}

    async def search_patterns(
        self,
        pattern_type: str,
        pattern_value: str,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for code patterns in the graph."""
        if pattern_type == "function_name":
            base_match = "MATCH (n:Function) WHERE n.name CONTAINS $pattern_value"
        elif pattern_type == "class_name":
            base_match = "MATCH (n:Class) WHERE n.name CONTAINS $pattern_value"
        elif pattern_type == "file_path":
            base_match = "MATCH (n) WHERE n.file_path CONTAINS $pattern_value"
        else:
            base_match = "MATCH (n) WHERE n.name CONTAINS $pattern_value"
        
        if project_id:
            # Use MATCH instead of EXISTS for Neo4j 5.x compatibility
            query = f"""
            {base_match}
            WITH n
            MATCH (p:Project {{id: $project_id}})-[:CONTAINS*]->(n)
            RETURN n.id as id, n.name as name, labels(n)[0] as type,
                   n.file_path as file_path, n.line_number as line_number
            LIMIT 50
            """
        else:
            query = f"""
            {base_match}
            RETURN n.id as id, n.name as name, labels(n)[0] as type,
                   n.file_path as file_path, n.line_number as line_number
            LIMIT 50
            """
        
        results = await self.client.execute_query(
            query,
            {"pattern_value": pattern_value, "project_id": project_id}
        )
        return results

    async def get_project_context(
        self,
        project_id: str,
        focus_components: Optional[List[str]] = None,
        include_dependencies: bool = True,
    ) -> Dict[str, Any]:
        """Get relevant context for agents working on a project."""
        context = {
            "project_id": project_id,
            "components": [],
            "functions": [],
            "classes": [],
            "dependencies": [],
        }
        
        # Get project overview
        project_query = """
        MATCH (p:Project {id: $project_id})
        OPTIONAL MATCH (p)-[:CONTAINS]->(c:Component)
        OPTIONAL MATCH (p)-[:CONTAINS]->(f:Function)
        OPTIONAL MATCH (p)-[:CONTAINS]->(cl:Class)
        RETURN p, 
               count(DISTINCT c) as component_count,
               count(DISTINCT f) as function_count,
               count(DISTINCT cl) as class_count
        """
        project_info = await self.client.execute_query(
            project_query,
            {"project_id": project_id}
        )
        
        if not project_info:
            return context
        
        # Get components
        if focus_components:
            component_query = """
            MATCH (p:Project {id: $project_id})-[:CONTAINS]->(c:Component)
            WHERE c.id IN $focus_components
            RETURN c.id as id, c.name as name, c.type as type, 
                   c.file_path as file_path, c.metadata as metadata
            """
            components = await self.client.execute_query(
                component_query,
                {"project_id": project_id, "focus_components": focus_components}
            )
        else:
            component_query = """
            MATCH (p:Project {id: $project_id})-[:CONTAINS]->(c:Component)
            RETURN c.id as id, c.name as name, c.type as type,
                   c.file_path as file_path, c.metadata as metadata
            LIMIT 100
            """
            components = await self.client.execute_query(
                component_query,
                {"project_id": project_id}
            )
        
        context["components"] = components
        
        # Get dependencies if requested
        if include_dependencies and components:
            component_ids = [c["id"] for c in components]
            dep_query = """
            MATCH (from:Component)-[r:DEPENDS_ON]->(to:Component)
            WHERE from.id IN $component_ids OR to.id IN $component_ids
            RETURN from.id as from_id, from.name as from_name,
                   to.id as to_id, to.name as to_name,
                   r.type as type
            """
            dependencies = await self.client.execute_query(
                dep_query,
                {"component_ids": component_ids}
            )
            context["dependencies"] = dependencies
        
        return context

    async def store_module(
        self,
        project_id: str,
        module_id: str,
        file_path: str,
        imports: List[str],
        exports: List[str],
    ) -> None:
        """Store a module node in the graph."""
        query = """
        MATCH (p:Project {id: $project_id})
        CREATE (m:Module {
            id: $module_id,
            file_path: $file_path,
            imports: $imports,
            exports: $exports,
            created_at: datetime()
        })
        CREATE (p)-[:CONTAINS]->(m)
        RETURN m
        """
        await self.client.execute_write(
            query,
            {
                "project_id": project_id,
                "module_id": module_id,
                "file_path": file_path,
                "imports": imports,
                "exports": exports,
            }
        )

    async def create_import_relationship(
        self,
        from_module_id: str,
        to_module_id: str,
        imported_names: List[str],
    ) -> None:
        """Create an IMPORTS relationship between modules."""
        query = """
        MATCH (from:Module {id: $from_id})
        MATCH (to:Module {id: $to_id})
        CREATE (from)-[r:IMPORTS {
            names: $imported_names,
            created_at: datetime()
        }]->(to)
        RETURN r
        """
        await self.client.execute_write(
            query,
            {
                "from_id": from_module_id,
                "to_id": to_module_id,
                "imported_names": imported_names,
            }
        )

    async def delete_component(self, component_id: str) -> None:
        """Delete a component and its relationships."""
        query = """
        MATCH (c:Component {id: $component_id})
        DETACH DELETE c
        """
        await self.client.execute_write(query, {"component_id": component_id})
        logger.info(f"Deleted component: {component_id}")

    async def clear_project(self, project_id: str) -> None:
        """Clear all data for a project."""
        await self.client.clear_project(project_id)

    # -------------------------------------------------------------------------
    # New node store methods (Req 13.1–13.4)
    # -------------------------------------------------------------------------

    async def store_requirement(
        self,
        project_id: str,
        text: str,
        source_agent: str,
    ) -> None:
        """Store a Requirement node linked to the project. Never raises."""
        try:
            query = """
            MATCH (p:Project {id: $project_id})
            CREATE (r:Requirement {
                id: $id,
                project_id: $project_id,
                text: $text,
                source_agent: $source_agent,
                created_at: datetime()
            })
            CREATE (p)-[:CONTAINS]->(r)
            """
            await self.client.execute_write(
                query,
                {
                    "id": str(uuid4()),
                    "project_id": project_id,
                    "text": text,
                    "source_agent": source_agent,
                },
            )
        except Exception as e:
            logger.warning(f"store_requirement failed (non-blocking): {e}")

    async def store_architecture_decision(
        self,
        project_id: str,
        title: str,
        decision: str,
        rationale: str,
        language: str,
        framework: str,
    ) -> None:
        """Store an ArchitectureDecision node linked to the project. Never raises."""
        try:
            query = """
            MATCH (p:Project {id: $project_id})
            CREATE (a:ArchitectureDecision {
                id: $id,
                project_id: $project_id,
                title: $title,
                decision: $decision,
                rationale: $rationale,
                language: $language,
                framework: $framework,
                created_at: datetime()
            })
            CREATE (p)-[:CONTAINS]->(a)
            """
            await self.client.execute_write(
                query,
                {
                    "id": str(uuid4()),
                    "project_id": project_id,
                    "title": title,
                    "decision": decision,
                    "rationale": rationale,
                    "language": language,
                    "framework": framework,
                },
            )
        except Exception as e:
            logger.warning(f"store_architecture_decision failed (non-blocking): {e}")

    async def store_pattern(
        self,
        project_id: str,
        name: str,
        description: str,
        language: str,
        code_snippet: str,
    ) -> None:
        """Store a Pattern node linked to the project. Never raises."""
        try:
            query = """
            MATCH (p:Project {id: $project_id})
            CREATE (pt:Pattern {
                id: $id,
                project_id: $project_id,
                name: $name,
                description: $description,
                language: $language,
                code_snippet: $code_snippet,
                created_at: datetime()
            })
            CREATE (p)-[:CONTAINS]->(pt)
            """
            await self.client.execute_write(
                query,
                {
                    "id": str(uuid4()),
                    "project_id": project_id,
                    "name": name,
                    "description": description,
                    "language": language,
                    "code_snippet": code_snippet,
                },
            )
        except Exception as e:
            logger.warning(f"store_pattern failed (non-blocking): {e}")

    async def store_error_fix(
        self,
        project_id: str,
        error_type: str,
        error_message: str,
        fix_description: str,
        fixed_code: str,
        language: str,
    ) -> None:
        """Store an ErrorFix node linked to the project. Never raises."""
        try:
            query = """
            MATCH (p:Project {id: $project_id})
            CREATE (ef:ErrorFix {
                id: $id,
                project_id: $project_id,
                error_type: $error_type,
                error_message: $error_message,
                fix_description: $fix_description,
                fixed_code: $fixed_code,
                language: $language,
                created_at: datetime()
            })
            CREATE (p)-[:CONTAINS]->(ef)
            """
            await self.client.execute_write(
                query,
                {
                    "id": str(uuid4()),
                    "project_id": project_id,
                    "error_type": error_type,
                    "error_message": error_message,
                    "fix_description": fix_description,
                    "fixed_code": fixed_code,
                    "language": language,
                },
            )
        except Exception as e:
            logger.warning(f"store_error_fix failed (non-blocking): {e}")

    async def get_context_for_agent(
        self,
        project_id: str,
        component_name: str,
        context_depth: int = 2
    ) -> Dict[str, Any]:
        """Compatibility alias for get_project_context with component-specific focus."""
        return await self.get_project_context(
            project_id=project_id,
            focus_components=[component_name] if component_name else None
        )


# Global Knowledge Graph service instance
knowledge_graph_service = KnowledgeGraphService()
