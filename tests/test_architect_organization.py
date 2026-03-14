"""
Tests for Architect Agent code organization and documentation capabilities.
"""

import pytest
import json
from foundry.agents.architect import ArchitectAgent
from foundry.agents.base import AgentType
from foundry.config import settings


@pytest.mark.asyncio
class TestArchitectOrganization:
    """Test suite for code organization and documentation features."""

    @pytest.fixture
    async def architect_agent(self):
        """Create an ArchitectAgent instance for testing."""
        return ArchitectAgent(model_name=settings.ollama_model_name)

    @pytest.fixture
    def sample_architecture(self):
        """Sample architecture for testing."""
        return {
            "pattern": "microservices",
            "components": ["api-gateway", "user-service", "order-service"],
            "technology_stack": {
                "frontend": "React",
                "backend": "Node.js",
                "database": "PostgreSQL"
            }
        }

    @pytest.fixture
    def sample_tech_stack(self):
        """Sample technology stack for testing."""
        return {
            "frontend": "React with TypeScript",
            "backend": "Node.js with Express",
            "database": "PostgreSQL",
            "cache": "Redis"
        }

    @pytest.fixture
    def sample_prd(self):
        """Sample PRD content for testing."""
        return """
        Product Requirements Document
        
        Project: E-commerce Platform
        
        Requirements:
        1. User authentication and authorization
        2. Product catalog management
        3. Shopping cart functionality
        4. Order processing
        5. Payment integration
        
        Non-functional Requirements:
        - Scalability: Support 10,000 concurrent users
        - Performance: Page load time < 2 seconds
        - Security: PCI DSS compliance for payments
        """

    async def test_organize_file_structure(self, architect_agent, sample_architecture, sample_tech_stack):
        """Test file structure generation following best practices."""
        result = await architect_agent.organize_file_structure(
            sample_architecture,
            sample_tech_stack
        )
        
        # Verify result structure
        assert isinstance(result, dict)
        assert "root_structure" in result or "directories" in result or "files" in result
        
        # If properly formatted, check for key components
        if "root_structure" in result:
            assert "directories" in result["root_structure"] or "files" in result["root_structure"]

    async def test_document_architectural_decisions(
        self, 
        architect_agent, 
        sample_architecture, 
        sample_tech_stack,
        sample_prd
    ):
        """Test ADR generation with rationale and trade-offs."""
        result = await architect_agent.document_architectural_decisions(
            sample_architecture,
            sample_tech_stack,
            sample_prd
        )
        
        # Verify result structure
        assert isinstance(result, dict)
        
        # Check for decisions array
        if "decisions" in result:
            assert isinstance(result["decisions"], list)
            
            # If decisions exist, verify structure
            if len(result["decisions"]) > 0:
                decision = result["decisions"][0]
                # ADR should have key fields
                assert any(key in decision for key in ["id", "title", "context", "decision"])

    async def test_track_rationale_and_tradeoffs(self, architect_agent):
        """Test detailed rationale and trade-off tracking."""
        decision_context = {
            "decision": "Use microservices architecture",
            "requirements": "High scalability, independent deployment",
            "constraints": "Team size: 5 developers, Timeline: 6 months"
        }
        
        result = await architect_agent.track_rationale_and_tradeoffs(
            "ADR-001",
            decision_context
        )
        
        # Verify result structure
        assert isinstance(result, dict)
        assert "decision_id" in result
        assert result["decision_id"] == "ADR-001"
        
        # Check for key analysis components
        assert any(key in result for key in ["rationale", "trade_offs", "future_implications"])

    async def test_generate_comprehensive_design(self, architect_agent, sample_prd):
        """Test comprehensive design generation including all components."""
        result = await architect_agent.generate_comprehensive_design(sample_prd)
        
        # Verify comprehensive design structure
        assert isinstance(result, dict)
        assert "architecture" in result
        assert "file_structure" in result
        assert "architectural_decisions" in result
        assert "metadata" in result
        
        # Verify metadata
        metadata = result["metadata"]
        assert "generated_at" in metadata
        assert "agent" in metadata
        assert "model" in metadata
        assert metadata["agent"] == str(AgentType.ARCHITECT)

    async def test_file_structure_best_practices(self, architect_agent, sample_architecture, sample_tech_stack):
        """Test that file structure follows best practices."""
        result = await architect_agent.organize_file_structure(
            sample_architecture,
            sample_tech_stack
        )
        
        # Verify conventions are documented
        if "conventions" in result:
            conventions = result["conventions"]
            assert isinstance(conventions, dict)
            # Should have some convention guidelines
            assert len(conventions) > 0

    async def test_adr_completeness(self, architect_agent, sample_architecture, sample_tech_stack, sample_prd):
        """Test that ADRs contain complete information."""
        result = await architect_agent.document_architectural_decisions(
            sample_architecture,
            sample_tech_stack,
            sample_prd
        )
        
        if "decisions" in result and len(result["decisions"]) > 0:
            decision = result["decisions"][0]
            
            # Check for comprehensive ADR fields
            expected_fields = ["context", "decision", "rationale", "consequences", "alternatives"]
            present_fields = [field for field in expected_fields if field in decision]
            
            # At least some key fields should be present
            assert len(present_fields) >= 2

    async def test_tradeoff_analysis_dimensions(self, architect_agent):
        """Test that trade-off analysis covers multiple dimensions."""
        decision_context = {
            "decision": "Use PostgreSQL for database",
            "alternatives": ["MongoDB", "MySQL"],
            "requirements": "ACID compliance, complex queries"
        }
        
        result = await architect_agent.track_rationale_and_tradeoffs(
            "ADR-002",
            decision_context
        )
        
        # Verify trade-off analysis structure
        if "trade_offs" in result:
            trade_offs = result["trade_offs"]
            assert isinstance(trade_offs, dict)
            
            # Should have some analysis dimensions
            if "dimensions" in trade_offs:
                assert isinstance(trade_offs["dimensions"], list)


@pytest.mark.asyncio
class TestArchitectIntegration:
    """Integration tests for architect agent with organization features."""

    @pytest.fixture
    async def architect_agent(self):
        """Create an ArchitectAgent instance for testing."""
        return ArchitectAgent(model_name=settings.ollama_model_name)

    async def test_end_to_end_design_generation(self, architect_agent):
        """Test complete design generation workflow."""
        prd = """
        Build a task management application with:
        - User authentication
        - Task CRUD operations
        - Task assignment to users
        - Due date tracking
        - Priority levels
        """
        
        # Generate comprehensive design
        design = await architect_agent.generate_comprehensive_design(prd)
        
        # Verify all components are present
        assert "architecture" in design
        assert "file_structure" in design
        assert "architectural_decisions" in design
        assert "metadata" in design
        
        # Verify design is actionable
        assert design["architecture"] is not None
        assert design["file_structure"] is not None
