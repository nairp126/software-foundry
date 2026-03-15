"""Ingestion pipeline for populating the Knowledge Graph."""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from uuid import uuid4

from foundry.graph.code_parser import python_parser, ParsedModule

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Pipeline for ingesting code into the Knowledge Graph."""
    
    def __init__(self):
        self.parser = python_parser
        self.logger = logger

    @property
    def kg_service(self):
        """Lazy load the knowledge graph service to prevent circular imports."""
        from foundry.services.knowledge_graph import knowledge_graph_service
        return knowledge_graph_service
    
    async def ingest_project(
        self,
        project_id: str,
        project_name: str,
        project_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ingest an entire project into the Knowledge Graph."""
        self.logger.info(f"Starting ingestion for project: {project_name}")
        
        stats = {
            "files_processed": 0,
            "functions_created": 0,
            "classes_created": 0,
            "modules_created": 0,
            "dependencies_created": 0,
            "errors": []
        }
        
        try:
            # Create project node
            await self.kg_service.create_project(
                project_id=project_id,
                name=project_name,
                metadata=metadata or {}
            )
            
            # Parse all Python files
            parsed_modules = self.parser.parse_directory(project_path)
            stats["files_processed"] = len(parsed_modules)
            
            # Create a mapping of file paths to module IDs
            module_id_map = {}
            
            # First pass: Create all modules, functions, and classes
            for file_path, module in parsed_modules.items():
                try:
                    module_id = str(uuid4())
                    module_id_map[file_path] = module_id
                    
                    # Create module node
                    await self.kg_service.store_module(
                        project_id=project_id,
                        module_id=module_id,
                        file_path=file_path,
                        imports=[imp.module for imp in module.imports],
                        exports=[func.name for func in module.functions] + 
                                [cls.name for cls in module.classes]
                    )
                    stats["modules_created"] += 1
                    
                    # Create component node for the file
                    component_id = str(uuid4())
                    await self.kg_service.store_component(
                        project_id=project_id,
                        component_id=component_id,
                        name=Path(file_path).stem,
                        component_type="module",
                        file_path=file_path,
                        metadata={
                            "docstring": module.docstring,
                            "global_variables": module.global_variables
                        }
                    )
                    
                    # Create function nodes
                    for func in module.functions:
                        function_id = str(uuid4())
                        await self.kg_service.store_function(
                            project_id=project_id,
                            function_id=function_id,
                            name=func.name,
                            signature=func.signature,
                            file_path=file_path,
                            line_number=func.line_number,
                            complexity=func.complexity,
                            parent_component_id=component_id,
                            content=func.content
                        )
                        stats["functions_created"] += 1
                    
                    # Create class nodes
                    for cls in module.classes:
                        class_id = str(uuid4())
                        await self.kg_service.store_class(
                            project_id=project_id,
                            class_id=class_id,
                            name=cls.name,
                            file_path=file_path,
                            line_number=cls.line_number,
                            methods=cls.methods,
                            base_classes=cls.base_classes,
                            parent_component_id=component_id,
                            content=cls.content
                        )
                        stats["classes_created"] += 1
                
                except Exception as e:
                    error_msg = f"Error processing {file_path}: {e}"
                    self.logger.error(error_msg)
                    stats["errors"].append(error_msg)
            
            # Second pass: Create relationships
            dependency_graph = self.parser.build_dependency_graph(parsed_modules)
            
            for file_path, dependencies in dependency_graph.items():
                if file_path not in module_id_map:
                    continue
                
                from_module_id = module_id_map[file_path]
                
                for dep_file_path in dependencies:
                    if dep_file_path not in module_id_map:
                        continue
                    
                    to_module_id = module_id_map[dep_file_path]
                    
                    try:
                        # Create import relationship
                        module = parsed_modules[file_path]
                        imported_names = []
                        for imp in module.imports:
                            if any(part in dep_file_path for part in imp.module.split('.')):
                                imported_names.extend(imp.names if imp.names else [imp.module])
                        
                        await self.kg_service.create_import_relationship(
                            from_module_id=from_module_id,
                            to_module_id=to_module_id,
                            imported_names=imported_names
                        )
                        stats["dependencies_created"] += 1
                    
                    except Exception as e:
                        error_msg = f"Error creating dependency {file_path} -> {dep_file_path}: {e}"
                        self.logger.error(error_msg)
                        stats["errors"].append(error_msg)
            
            self.logger.info(f"Ingestion complete: {stats}")
            return stats
        
        except Exception as e:
            self.logger.error(f"Fatal error during ingestion: {e}")
            stats["errors"].append(str(e))
            return stats
    
    async def ingest_file(
        self,
        project_id: str,
        file_path: str,
        update_existing: bool = True
    ) -> Dict[str, Any]:
        """Ingest a single file into the Knowledge Graph."""
        self.logger.info(f"Ingesting file: {file_path}")
        
        stats = {
            "functions_created": 0,
            "classes_created": 0,
            "success": False,
            "error": None
        }
        
        try:
            # Parse the file
            module = self.parser.parse_file(file_path)
            if not module:
                stats["error"] = "Failed to parse file"
                return stats
            
            # If updating, delete existing component first
            if update_existing:
                # This is a simplified approach - in production you'd want to
                # query for existing components and update them
                pass
            
            # Create component node
            component_id = str(uuid4())
            await self.kg_service.store_component(
                project_id=project_id,
                component_id=component_id,
                name=Path(file_path).stem,
                component_type="module",
                file_path=file_path,
                metadata={
                    "docstring": module.docstring,
                    "global_variables": module.global_variables
                }
            )
            
            # Create function nodes
            for func in module.functions:
                function_id = str(uuid4())
                await self.kg_service.store_function(
                    project_id=project_id,
                    function_id=function_id,
                    name=func.name,
                    signature=func.signature,
                    file_path=file_path,
                    line_number=func.line_number,
                    complexity=func.complexity,
                    parent_component_id=component_id
                )
                stats["functions_created"] += 1
            
            # Create class nodes
            for cls in module.classes:
                class_id = str(uuid4())
                await self.kg_service.store_class(
                    project_id=project_id,
                    class_id=class_id,
                    name=cls.name,
                    file_path=file_path,
                    line_number=cls.line_number,
                    methods=cls.methods,
                    base_classes=cls.base_classes,
                    parent_component_id=component_id
                )
                stats["classes_created"] += 1
            
            stats["success"] = True
            self.logger.info(f"File ingestion complete: {stats}")
            return stats
        
        except Exception as e:
            error_msg = f"Error ingesting file {file_path}: {e}"
            self.logger.error(error_msg)
            stats["error"] = str(e)
            return stats
    
    async def update_relationships(
        self,
        project_id: str,
        file_path: str,
        parsed_modules: Dict[str, ParsedModule]
    ) -> int:
        """Update relationships after file changes."""
        relationships_created = 0
        
        try:
            # Build dependency graph
            dependency_graph = self.parser.build_dependency_graph(parsed_modules)
            
            if file_path not in dependency_graph:
                return 0
            
            # Get the module ID for this file
            # In a real implementation, you'd query the graph for this
            # For now, we'll skip this as it requires more complex logic
            
            self.logger.info(f"Updated relationships for {file_path}")
            return relationships_created
        
        except Exception as e:
            self.logger.error(f"Error updating relationships: {e}")
            return 0
    
    async def handle_file_deletion(
        self,
        project_id: str,
        file_path: str
    ) -> bool:
        """Handle deletion of a file from the project."""
        try:
            # Query for components with this file path
            query = """
            MATCH (c:Component {file_path: $file_path})
            WHERE EXISTS((c)<-[:CONTAINS]-(:Project {id: $project_id}))
            DETACH DELETE c
            """
            
            await self.kg_service.client.execute_write(
                query,
                {"project_id": project_id, "file_path": file_path}
            )
            
            self.logger.info(f"Deleted components for file: {file_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    async def refresh_project(
        self,
        project_id: str,
        project_path: str
    ) -> Dict[str, Any]:
        """Refresh the entire project in the graph."""
        self.logger.info(f"Refreshing project: {project_id}")
        
        # Clear existing data
        await self.kg_service.clear_project(project_id)
        
        # Re-ingest
        return await self.ingest_project(
            project_id=project_id,
            project_name=Path(project_path).name,
            project_path=project_path
        )


# Global ingestion pipeline instance
ingestion_pipeline = IngestionPipeline()
