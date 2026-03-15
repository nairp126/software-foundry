"""Neo4j client for Knowledge Graph operations."""

import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import ServiceUnavailable, AuthError

from foundry.config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Async Neo4j client for Knowledge Graph operations."""

    def __init__(self):
        """Initialize Neo4j client."""
        self._driver: Optional[AsyncDriver] = None
        self._uri = settings.neo4j_uri
        self._user = settings.neo4j_user
        self._password = settings.neo4j_password
        self.logger = logger

    async def connect(self) -> None:
        """Establish connection to Neo4j database."""
        try:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )
            # Verify connectivity
            await self._driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self._uri}")
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def disconnect(self) -> None:
        """Close connection to Neo4j database."""
        if self._driver:
            await self._driver.close()
            logger.info("Disconnected from Neo4j")

    @asynccontextmanager
    async def session(self) -> AsyncSession:
        """Get a Neo4j session context manager."""
        if not self._driver:
            await self.connect()
        
        async with self._driver.session() as session:
            yield session

    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a write query and return summary."""
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            summary = await result.consume()
            return {
                "nodes_created": summary.counters.nodes_created,
                "relationships_created": summary.counters.relationships_created,
                "properties_set": summary.counters.properties_set,
                "nodes_deleted": summary.counters.nodes_deleted,
                "relationships_deleted": summary.counters.relationships_deleted,
            }

    async def create_constraints(self) -> None:
        """Create database constraints and indexes."""
        constraints = [
            # Unique constraints
            "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT component_id IF NOT EXISTS FOR (c:Component) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT function_id IF NOT EXISTS FOR (f:Function) REQUIRE f.id IS UNIQUE",
            "CREATE CONSTRAINT class_id IF NOT EXISTS FOR (c:Class) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT module_id IF NOT EXISTS FOR (m:Module) REQUIRE m.id IS UNIQUE",
            # New node type constraints (Req 13.5)
            "CREATE CONSTRAINT requirement_id IF NOT EXISTS FOR (r:Requirement) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT architecture_decision_id IF NOT EXISTS FOR (a:ArchitectureDecision) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT pattern_id IF NOT EXISTS FOR (p:Pattern) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT error_fix_id IF NOT EXISTS FOR (e:ErrorFix) REQUIRE e.id IS UNIQUE",
            
            # Indexes for performance
            "CREATE INDEX project_name IF NOT EXISTS FOR (p:Project) ON (p.name)",
            "CREATE INDEX component_name IF NOT EXISTS FOR (c:Component) ON (c.name)",
            "CREATE INDEX function_name IF NOT EXISTS FOR (f:Function) ON (f.name)",
            "CREATE INDEX class_name IF NOT EXISTS FOR (c:Class) ON (c.name)",
            "CREATE INDEX module_path IF NOT EXISTS FOR (m:Module) ON (m.file_path)",
        ]
        
        for constraint in constraints:
            try:
                await self.execute_write(constraint)
                logger.info(f"Created constraint/index: {constraint[:50]}...")
            except Exception as e:
                logger.warning(f"Constraint/index already exists or failed: {e}")

    async def clear_project(self, project_id: str) -> None:
        """Delete all nodes and relationships for a project."""
        query = """
        MATCH (p:Project {id: $project_id})
        OPTIONAL MATCH (p)-[*]-(n)
        DETACH DELETE p, n
        """
        await self.execute_write(query, {"project_id": project_id})
        logger.info(f"Cleared project {project_id} from graph")

    async def health_check(self) -> bool:
        """Check if Neo4j is accessible."""
        try:
            result = await self.execute_query("RETURN 1 as health")
            return len(result) > 0
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False


# Global Neo4j client instance
neo4j_client = Neo4jClient()
