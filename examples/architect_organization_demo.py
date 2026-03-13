"""
Demo script for Architect Agent code organization and documentation features.

This script demonstrates:
1. File structure generation following best practices
2. Architectural decision documentation (ADRs)
3. Rationale and trade-off tracking
4. Comprehensive design generation
"""

import asyncio
import json
from foundry.agents.architect import ArchitectAgent


async def demo_file_structure_generation():
    """Demonstrate file structure generation."""
    print("\n" + "="*80)
    print("DEMO 1: File Structure Generation")
    print("="*80)
    
    architect = ArchitectAgent(model_name="qwen2.5-coder:7b")
    
    architecture = {
        "pattern": "monolithic",
        "layers": ["presentation", "business", "data"],
        "technology_stack": {
            "frontend": "React with TypeScript",
            "backend": "Python FastAPI",
            "database": "PostgreSQL"
        }
    }
    
    tech_stack = {
        "frontend": "React with TypeScript",
        "backend": "Python FastAPI",
        "database": "PostgreSQL",
        "cache": "Redis"
    }
    
    print("\nGenerating file structure for:")
    print(json.dumps(architecture, indent=2))
    
    file_structure = await architect.organize_file_structure(architecture, tech_stack)
    
    print("\nGenerated File Structure:")
    print(json.dumps(file_structure, indent=2))


async def demo_architectural_decisions():
    """Demonstrate ADR generation."""
    print("\n" + "="*80)
    print("DEMO 2: Architectural Decision Records (ADRs)")
    print("="*80)
    
    architect = ArchitectAgent(model_name="qwen2.5-coder:7b")
    
    architecture = {
        "pattern": "microservices",
        "services": ["user-service", "order-service", "payment-service"],
        "technology_stack": {
            "backend": "Node.js",
            "database": "PostgreSQL",
            "message_queue": "RabbitMQ"
        }
    }
    
    tech_stack = {
        "backend": "Node.js with Express",
        "database": "PostgreSQL",
        "message_queue": "RabbitMQ"
    }
    
    requirements = """
    E-commerce platform requirements:
    - Handle 10,000 concurrent users
    - Process payments securely
    - Support multiple payment methods
    - Real-time order tracking
    - Scalable architecture
    """
    
    print("\nGenerating ADRs for:")
    print(f"Architecture: {architecture['pattern']}")
    print(f"Requirements: {requirements[:100]}...")
    
    adrs = await architect.document_architectural_decisions(
        architecture,
        tech_stack,
        requirements
    )
    
    print("\nGenerated Architectural Decision Records:")
    print(json.dumps(adrs, indent=2))


async def demo_tradeoff_tracking():
    """Demonstrate rationale and trade-off tracking."""
    print("\n" + "="*80)
    print("DEMO 3: Rationale and Trade-off Tracking")
    print("="*80)
    
    architect = ArchitectAgent(model_name="qwen2.5-coder:7b")
    
    decision_context = {
        "decision": "Use microservices architecture instead of monolith",
        "requirements": [
            "High scalability",
            "Independent deployment of services",
            "Team autonomy"
        ],
        "constraints": [
            "Team size: 8 developers",
            "Timeline: 6 months",
            "Budget: Limited"
        ],
        "alternatives": [
            "Monolithic architecture",
            "Modular monolith"
        ]
    }
    
    print("\nAnalyzing decision:")
    print(json.dumps(decision_context, indent=2))
    
    analysis = await architect.track_rationale_and_tradeoffs(
        "ADR-001",
        decision_context
    )
    
    print("\nTrade-off Analysis:")
    print(json.dumps(analysis, indent=2))


async def demo_comprehensive_design():
    """Demonstrate comprehensive design generation."""
    print("\n" + "="*80)
    print("DEMO 4: Comprehensive Design Generation")
    print("="*80)
    
    architect = ArchitectAgent(model_name="qwen2.5-coder:7b")
    
    prd = """
    Product Requirements Document: Task Management System
    
    Functional Requirements:
    1. User authentication and authorization
    2. Create, read, update, delete tasks
    3. Assign tasks to team members
    4. Set due dates and priorities
    5. Track task status (todo, in-progress, done)
    6. Comment on tasks
    7. File attachments
    
    Non-Functional Requirements:
    - Support 1,000 concurrent users
    - Response time < 500ms for API calls
    - 99.9% uptime
    - Mobile-responsive UI
    - WCAG 2.1 AA accessibility compliance
    
    Technical Constraints:
    - Must use existing PostgreSQL database
    - Deploy on AWS
    - Budget: $500/month for infrastructure
    """
    
    print("\nGenerating comprehensive design for:")
    print(prd[:200] + "...")
    
    design = await architect.generate_comprehensive_design(prd)
    
    print("\nComprehensive Design Generated:")
    print(f"- Architecture: {len(str(design['architecture']))} chars")
    print(f"- File Structure: {len(str(design['file_structure']))} chars")
    print(f"- ADRs: {len(design['architectural_decisions'].get('decisions', []))} decisions")
    print(f"- Metadata: {design['metadata']}")
    
    print("\nSample from design:")
    print(json.dumps({
        "architecture_sample": str(design['architecture'])[:200] + "...",
        "metadata": design['metadata']
    }, indent=2))


async def main():
    """Run all demos."""
    print("\n" + "="*80)
    print("ARCHITECT AGENT: Code Organization & Documentation Demo")
    print("="*80)
    
    try:
        await demo_file_structure_generation()
        await demo_architectural_decisions()
        await demo_tradeoff_tracking()
        await demo_comprehensive_design()
        
        print("\n" + "="*80)
        print("All demos completed successfully!")
        print("="*80)
        
    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
