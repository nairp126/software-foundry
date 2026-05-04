import logging
from typing import Dict, List, Set, Any
from foundry.tools.knowledge_graph_tools import KnowledgeGraphTools

logger = logging.getLogger(__name__)

class KGImpactGuard:
    """
    Monitors code modifications and uses the Knowledge Graph to identify 
    downstream impact on other files, ensuring synchronization across the project.
    """
    
    def __init__(self):
        self.kg_tools = KnowledgeGraphTools()
        self.max_depth = 2
        
    async def get_affected_files(self, project_id: str, modified_files: Set[str]) -> Set[str]:
        """
        Calculates which files are impacted by changes in the modified_files set.
        """
        affected_files = set()
        
        try:
            await self.kg_tools.connect()
            
            for filename in modified_files:
                # 1. Get all components defined in this file
                components = await self.kg_tools.get_file_components(project_id, filename)
                
                for component in components:
                    comp_name = component.get("name")
                    if not comp_name:
                        continue
                        
                    # 2. Analyze impact of this component
                    impact = await self.kg_tools.analyze_change_impact(
                        project_id=project_id,
                        component_name=comp_name,
                        max_depth=self.max_depth
                    )
                    
                    # 3. Extract file paths from impacted components
                    for node in impact.get("affected_nodes", []):
                        path = node.get("file_path")
                        if path and path != filename:
                            affected_files.add(path)
                            
            return affected_files
            
        except Exception as e:
            logger.warning(f"Impact Analysis failed: {e}")
            return set()
        finally:
            await self.kg_tools.disconnect()

    async def synchronize_project_state(self, project_id: str, code_repo: Dict[str, str], modified_files: Set[str]) -> List[str]:
        """
        Identifies files that need to be re-reviewed or updated based on KG impact.
        Returns a list of filenames that require attention.
        """
        affected = await self.get_affected_files(project_id, modified_files)
        
        # Filter: only include files that actually exist in the current repo
        to_sync = [f for f in affected if f in code_repo]
        
        if to_sync:
            logger.info(f"KG Impact Guard: Identified {len(to_sync)} files requiring sync: {to_sync}")
            
        return to_sync
