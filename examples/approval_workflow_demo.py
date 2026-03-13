"""
Demonstration of the Approval Workflow System.

This example shows how to:
1. Create approval requests with detailed content
2. Respond to approvals (approve, reject, approve with changes)
3. Handle approval timeouts
4. Use pause/resume/cancel controls
5. Manage checkpoints for state preservation
"""

import asyncio
import uuid
from datetime import datetime, timedelta

from foundry.database import AsyncSessionLocal
from foundry.models.project import Project, ProjectStatus
from foundry.models.approval import (
    ApprovalType,
    ApprovalPolicy,
    ApprovalContent,
    ApprovalResponse,
    ApprovalRequestCreate,
)
from foundry.services.approval_service import approval_service
from foundry.services.agent_control import agent_control_service
from foundry.redis_client import redis_client


async def demo_basic_approval_workflow():
    """Demonstrate basic approval request and response."""
    print("\n=== Basic Approval Workflow Demo ===\n")
    
    async with AsyncSessionLocal() as session:
        # Create a test project
        project = Project(
            name="E-Commerce Platform",
            description="Full-stack e-commerce application",
            requirements="Build an online store with product catalog and checkout",
            status=ProjectStatus.created,
            approval_policy=ApprovalPolicy.standard,
        )
        session.add(project)
        await session.flush()
        
        print(f"Created project: {project.name} (ID: {project.id})")
        print(f"Approval policy: {project.approval_policy.value}\n")
        
        # Create approval request
        content = ApprovalContent(
            description="Initial project plan for e-commerce platform",
            phantom_file_tree={
                "backend": {
                    "src": {
                        "api": {"products.py": "file", "orders.py": "file"},
                        "models": {"product.py": "file", "order.py": "file"},
                    },
                    "tests": {"test_api.py": "file"},
                },
                "frontend": {
                    "src": {
                        "components": {"ProductList.tsx": "file", "Cart.tsx": "file"},
                        "pages": {"Home.tsx": "file", "Checkout.tsx": "file"},
                    },
                },
            },
            technology_stack={
                "backend": "FastAPI 0.109.0",
                "frontend": "React 18.2.0",
                "database": "PostgreSQL 15",
                "cache": "Redis 7",
            },
            dependencies=[
                "fastapi",
                "sqlalchemy",
                "pydantic",
                "react",
                "typescript",
            ],
            cloud_resources=[
                {
                    "type": "EC2",
                    "instance_type": "t3.small",
                    "monthly_cost": 17.00,
                },
                {
                    "type": "RDS",
                    "instance_type": "db.t3.micro",
                    "monthly_cost": 15.00,
                },
                {
                    "type": "ElastiCache",
                    "node_type": "cache.t3.micro",
                    "monthly_cost": 12.00,
                },
            ],
            estimated_time="45 minutes",
        )
        
        request_data = ApprovalRequestCreate(
            project_id=str(project.id),
            request_type=ApprovalType.plan,
            content=content,
            estimated_cost=44.00,
            timeout_minutes=60,
        )
        
        approval = await approval_service.create_approval_request(session, request_data)
        await session.commit()
        
        print(f"Created approval request: {approval.id}")
        print(f"Type: {approval.request_type.value}")
        print(f"Status: {approval.status.value}")
        print(f"Estimated cost: ${approval.estimated_cost}/month")
        print(f"Timeout at: {approval.timeout_at}\n")
        
        # Simulate user approval
        print("User reviewing plan...")
        print("Decision: Approve\n")
        
        response = ApprovalResponse(
            decision="approve",
            reason="Plan looks comprehensive, proceed with execution",
        )
        
        result = await approval_service.respond_to_approval(
            session,
            approval.id,
            response,
        )
        await session.commit()
        
        print(f"Approval response: {result['status']}")
        print(f"Success: {result['success']}\n")


async def demo_approval_with_modifications():
    """Demonstrate approval with user modifications."""
    print("\n=== Approval with Modifications Demo ===\n")
    
    async with AsyncSessionLocal() as session:
        # Create project
        project = Project(
            name="Blog Platform",
            requirements="Build a blogging platform",
            approval_policy=ApprovalPolicy.standard,
        )
        session.add(project)
        await session.flush()
        
        # Create approval
        content = ApprovalContent(
            description="Blog platform plan",
            technology_stack={
                "backend": "Django 4.2",
                "database": "MySQL 8.0",
            },
        )
        
        request_data = ApprovalRequestCreate(
            project_id=str(project.id),
            request_type=ApprovalType.plan,
            content=content,
        )
        
        approval = await approval_service.create_approval_request(session, request_data)
        await session.commit()
        
        print(f"Original plan:")
        print(f"  Backend: Django 4.2")
        print(f"  Database: MySQL 8.0\n")
        
        # User approves with changes
        print("User decision: Approve with changes")
        print("Modifications: Switch to FastAPI and PostgreSQL\n")
        
        response = ApprovalResponse(
            decision="approve_with_changes",
            modifications={
                "technology_stack": {
                    "backend": "FastAPI 0.109.0",
                    "database": "PostgreSQL 15",
                }
            },
            reason="Prefer FastAPI for async support and PostgreSQL for better JSON handling",
        )
        
        result = await approval_service.respond_to_approval(
            session,
            approval.id,
            response,
        )
        await session.commit()
        
        print(f"Approval status: {result['status']}")
        print(f"Modified plan will be used for execution\n")


async def demo_pause_resume_workflow():
    """Demonstrate pause and resume functionality."""
    print("\n=== Pause/Resume Workflow Demo ===\n")
    
    await redis_client.connect()
    
    try:
        project_id = uuid.uuid4()
        print(f"Project ID: {project_id}\n")
        
        # Simulate execution in progress
        print("Agent execution in progress...")
        agent_state = {
            "current_agent": "engineer",
            "completed_steps": ["requirements", "architecture", "database_schema"],
            "current_step": "api_implementation",
            "progress_percent": 60,
        }
        
        # Save checkpoint
        await agent_control_service.save_checkpoint(
            project_id,
            agent_state,
            description="API implementation 60% complete",
        )
        print("Checkpoint saved\n")
        
        # User pauses execution
        print("User action: Pause execution")
        pause_result = await agent_control_service.pause_execution(
            project_id,
            reason="Need to review API design before continuing",
        )
        print(f"Pause result: {pause_result['message']}\n")
        
        # Check control status
        status = await agent_control_service.check_control_status(project_id)
        print(f"Control status: {status['action']}")
        print(f"Reason: {status['reason']}\n")
        
        # Simulate time passing while user reviews
        print("User reviewing progress...\n")
        
        # User resumes execution
        print("User action: Resume execution")
        resume_result = await agent_control_service.resume_execution(project_id)
        print(f"Resume result: {resume_result['message']}\n")
        
        # Restore checkpoint
        checkpoint = await agent_control_service.get_checkpoint(project_id)
        print(f"Restored checkpoint from: {checkpoint['timestamp']}")
        print(f"Resuming from: {checkpoint['agent_state']['current_step']}")
        print(f"Progress: {checkpoint['agent_state']['progress_percent']}%\n")
        
    finally:
        await redis_client.disconnect()


async def demo_timeout_handling():
    """Demonstrate approval timeout and auto-cancellation."""
    print("\n=== Timeout Handling Demo ===\n")
    
    async with AsyncSessionLocal() as session:
        # Create project
        project = Project(
            name="Timeout Test Project",
            requirements="Test timeout handling",
            approval_policy=ApprovalPolicy.standard,
        )
        session.add(project)
        await session.flush()
        
        # Create approval with short timeout
        content = ApprovalContent(
            description="Time-sensitive deployment approval",
        )
        
        request_data = ApprovalRequestCreate(
            project_id=str(project.id),
            request_type=ApprovalType.deployment,
            content=content,
            timeout_minutes=1,  # 1 minute timeout
        )
        
        approval = await approval_service.create_approval_request(session, request_data)
        await session.commit()
        
        print(f"Created approval with 1 minute timeout")
        print(f"Timeout at: {approval.timeout_at}\n")
        
        # Manually expire it for demo
        approval.timeout_at = datetime.utcnow() - timedelta(seconds=1)
        await session.commit()
        
        print("Simulating timeout expiration...")
        print("Background task processing expired approvals...\n")
        
        # Process expired approvals
        result = await approval_service.process_expired_approvals(session)
        await session.commit()
        
        print(f"Expired approvals processed: {result['expired_count']}")
        print(f"Auto-cancelled approval IDs: {result['approval_ids']}\n")
        
        # Verify status
        updated = await approval_service.get_approval_request(session, approval.id)
        print(f"Approval status: {updated.status.value}")
        print(f"Response: {updated.response}\n")


async def demo_policy_enforcement():
    """Demonstrate approval policy enforcement."""
    print("\n=== Approval Policy Enforcement Demo ===\n")
    
    policies = [
        (ApprovalPolicy.autonomous, "Autonomous Mode (Dev/Test)"),
        (ApprovalPolicy.standard, "Standard Mode (Default)"),
        (ApprovalPolicy.strict, "Strict Mode (High Security)"),
    ]
    
    approval_types = [
        ApprovalType.plan,
        ApprovalType.component,
        ApprovalType.deployment,
    ]
    
    for policy, policy_name in policies:
        print(f"{policy_name}:")
        for approval_type in approval_types:
            required = approval_service.should_request_approval(policy, approval_type)
            status = "REQUIRED" if required else "SKIPPED"
            print(f"  {approval_type.value}: {status}")
        print()


async def main():
    """Run all demos."""
    print("=" * 60)
    print("Approval Workflow System Demonstration")
    print("=" * 60)
    
    await demo_basic_approval_workflow()
    await demo_approval_with_modifications()
    await demo_pause_resume_workflow()
    await demo_timeout_handling()
    await demo_policy_enforcement()
    
    print("=" * 60)
    print("Demo Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
