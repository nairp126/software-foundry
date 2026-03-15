"""Knowledge Graph tools for agent use.

These tools allow agents to query the knowledge graph for context,
dependencies, and impact analysis.
"""

from typing import List, Dict, Any, Optional
from foundry.services.knowledge_graph import KnowledgeGraphService
from foundry.config import settings


class KnowledgeGraphTools:
    """Tools for agents to interact with the knowledge graph."""
    
    def __init__(self):
        self.kg_service = KnowledgeGraphService()
    
    async def connect(self):
        """Connect to Neo4j."""
        await self.kg_service.client.connect()
    
    async def disconnect(self):
        """Disconnect from Neo4j."""
        await self.kg_service.client.disconnect()
    
    async def find_function_dependencies(
        self,
        project_id: str,
        function_name: str,
        max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """Find all dependencies of a function.
        
        Args:
            project_id: Project identifier
            function_name: Name of the function to analyze
            max_depth: Maximum depth to traverse
            
        Returns:
            List of dependency information
        """
        return await self.kg_service.find_dependencies(
            project_id=project_id,
            component_name=function_name,
            max_depth=max_depth
        )
    
    async def analyze_change_impact(
        self,
        project_id: str,
        component_name: str,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """Analyze the impact of changing a component.
        
        Args:
            project_id: Project identifier
            component_name: Name of component to analyze
            max_depth: Maximum depth to traverse
            
        Returns:
            Impact analysis with affected components
        """
        return await self.kg_service.analyze_impact(
            project_id=project_id,
            component_name=component_name,
            max_depth=max_depth
        )
    
    async def find_callers(
        self,
        project_id: str,
        function_name: str
    ) -> List[Dict[str, Any]]:
        """Find all functions that call a specific function.
        
        Args:
            project_id: Project identifier
            function_name: Name of the function
            
        Returns:
            List of caller information
        """
        query = """
        MATCH (project:Project {project_id: $project_id})
        MATCH (project)-[:CONTAINS*]->(caller)
        MATCH (project)-[:CONTAINS*]->(callee:Function {name: $function_name})
        MATCH (caller)-[:CALLS]->(callee)
        RETURN caller.name as caller_name, 
               caller.type as caller_type,
               caller.file_path as file_path
        """
        
        results = await self.kg_service.client.execute_query(
            query,
            project_id=project_id,
            function_name=function_name
        )
        
        return [dict(record) for record in results]
    
    async def search_by_pattern(
        self,
        project_id: str,
        pattern: str,
        node_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for components matching a pattern.
        
        Args:
            project_id: Project identifier
            pattern: Regex pattern to match
            node_type: Optional node type filter (Function, Class, Module)
            
        Returns:
            List of matching components
        """
        return await self.kg_service.search_patterns(
            project_id=project_id,
            pattern=pattern,
            node_type=node_type
        )
    
    async def get_component_context(
        self,
        project_id: str,
        component_name: str,
        context_depth: int = 2
    ) -> Dict[str, Any]:
        """Get contextual information about a component.
        
        This includes the component itself, its dependencies,
        dependents, and related components.
        
        Args:
            project_id: Project identifier
            component_name: Name of the component
            context_depth: Depth of context to retrieve
            
        Returns:
            Comprehensive context information
        """
        return await self.kg_service.get_context_for_agent(
            project_id=project_id,
            component_name=component_name,
            context_depth=context_depth
        )
    
    async def get_file_components(
        self,
        project_id: str,
        file_path: str
    ) -> List[Dict[str, Any]]:
        """Get all components defined in a file.
        
        Args:
            project_id: Project identifier
            file_path: Path to the file
            
        Returns:
            List of components in the file
        """
        query = """
        MATCH (project:Project {project_id: $project_id})
        MATCH (project)-[:CONTAINS*]->(component)
        WHERE component.file_path = $file_path
        RETURN component.name as name,
               component.type as type,
               component.line_start as line_start,
               component.line_end as line_end,
               component.complexity as complexity
        ORDER BY component.line_start
        """
        
        results = await self.kg_service.client.execute_query(
            query,
            project_id=project_id,
            file_path=file_path
        )
        
        return [dict(record) for record in results]
    
    async def get_high_complexity_components(
        self,
        project_id: str,
        min_complexity: int = 10
    ) -> List[Dict[str, Any]]:
        """Find components with high cyclomatic complexity.
        
        Args:
            project_id: Project identifier
            min_complexity: Minimum complexity threshold
            
        Returns:
            List of high-complexity components
        """
        query = """
        MATCH (project:Project {project_id: $project_id})
        MATCH (project)-[:CONTAINS*]->(component:Function)
        WHERE component.complexity >= $min_complexity
        RETURN component.name as name,
               component.file_path as file_path,
               component.complexity as complexity,
               component.line_start as line_start
        ORDER BY component.complexity DESC
        """
        
        results = await self.kg_service.client.execute_query(
            query,
            project_id=project_id,
            min_complexity=min_complexity
        )
        
        return [dict(record) for record in results]
    
    async def get_surgical_context(
        self,
        project_id: str,
        dependency_names: List[str],
        max_snippet_chars: int = 1500
    ) -> str:
        """Retrieve source code snippets for specific dependencies from the KG.
        
        This is the core GraphRAG retrieval: instead of passing ALL previously
        generated code (which bloats the context window), we query the graph
        for ONLY the specific functions/classes that the current file depends on.
        
        Args:
            project_id: Project identifier
            dependency_names: List of function/class names to retrieve
            max_snippet_chars: Max chars per snippet to stay within context limits
            
        Returns:
            Formatted string of dependency source code for LLM injection
        """
        if not dependency_names:
            return ""
        
        query = """
        MATCH (project:Project {project_id: $project_id})
        MATCH (project)-[:CONTAINS*]->(node)
        WHERE node.name IN $names AND node.content IS NOT NULL AND node.content <> ''
        RETURN node.name as name, 
               node.file_path as file_path,
               node.content as content,
               labels(node)[0] as type
        """
        
        try:
            results = await self.kg_service.client.execute_query(
                query,
                project_id=project_id,
                names=dependency_names
            )
            
            if not results:
                return ""
            
            context_parts = []
            for record in results:
                name = record.get("name", "unknown")
                file_path = record.get("file_path", "unknown")
                node_type = record.get("type", "Component")
                content = record.get("content", "")
                
                # Truncate individual snippets if very large
                if len(content) > max_snippet_chars:
                    content = content[:max_snippet_chars] + "\n    # ... [truncated]"
                
                context_parts.append(
                    f"# [{node_type}] {name} (from {file_path})\n{content}"
                )
            
            if context_parts:
                header = "\n\nKNOWLEDGE GRAPH CONTEXT — Existing Dependencies:\n"
                header += "The following are REAL implementations already in the project. "
                header += "You MUST be compatible with these signatures and patterns.\n\n"
                return header + "\n\n".join(context_parts)
            
            return ""
            
        except Exception as e:
            self.kg_service.client.logger.error(f"Surgical context retrieval failed: {e}")
            return ""

    async def get_project_file_map(
        self,
        project_id: str
    ) -> List[Dict[str, Any]]:
        """Get a lightweight map of all files and their exported symbols.
        
        This gives the engineer a 'table of contents' of what already exists
        without needing the full source code of every file.
        
        Args:
            project_id: Project identifier
            
        Returns:
            List of file summaries with their exported symbols
        """
        query = """
        MATCH (project:Project {project_id: $project_id})
        MATCH (project)-[:CONTAINS*]->(m:Module)
        RETURN m.file_path as file_path, 
               m.exports as exports,
               m.imports as imports
        """
        
        try:
            results = await self.kg_service.client.execute_query(
                query,
                project_id=project_id
            )
            return [dict(record) for record in results]
        except Exception:
            return []

    def format_for_llm(self, data: Any) -> str:
        """Format knowledge graph data for LLM consumption.
        
        Args:
            data: Data from knowledge graph queries
            
        Returns:
            Formatted string for LLM context
        """
        if isinstance(data, list):
            if not data:
                return "No results found."
            
            formatted = []
            for item in data:
                if isinstance(item, dict):
                    parts = [f"{k}: {v}" for k, v in item.items()]
                    formatted.append(" | ".join(parts))
                else:
                    formatted.append(str(item))
            
            return "\n".join(formatted)
        
        elif isinstance(data, dict):
            if "affected_components" in data:
                # Impact analysis format
                affected = data.get("affected_components", [])
                return f"Impact Analysis:\n- Affected components: {len(affected)}\n" + \
                       "\n".join([f"  - {c.get('name')} ({c.get('type')})" for c in affected[:10]])
            
            # Generic dict format
            return "\n".join([f"{k}: {v}" for k, v in data.items()])
        
        return str(data)


# Singleton instance
kg_tools = KnowledgeGraphTools()
