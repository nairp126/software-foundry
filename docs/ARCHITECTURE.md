# System Architecture

## Architecture Diagram

```mermaid
graph TD
    User([User]) --> |Natural Language Request| API[FastAPI Gateway]
    
    subgraph "Autonomous Software Foundry Core"
        API --> Orchestrator[LangGraph Orchestrator]
        
        subgraph "Agent State Machine"
            Orchestrator --> PM[Product Manager Agent]
            PM --> |PRD| Architect[Architect Agent]
            Architect --> |Tech Stack & DB Schema| Engineer[Engineering Agent]
            Engineer --> |Source Code| Reviewer[Code Review Agent]
            Reviewer --> |Approved Code| DevOps[DevOps Agent]
            
            Reviewer --> |Feedback| Engineer
            
            Engineer -.-> |Execution Tests| Reflexion[Reflexion Engine]
            Reflexion -.-> |Stack Traces & Fixes| Engineer
        end
    end

    subgraph "Execution Environment"
        Reflexion --> Sandbox[Docker Sandbox]
        Sandbox --> |Metrics/Errors| Reflexion
    end

    subgraph "Data & Memory Layer"
        Orchestrator --> Postgres[(PostgreSQL)]
        Orchestrator --> Redis[(Redis Broker/Cache)]
        Orchestrator --> Neo4j[(Neo4j Knowledge Graph)]
    end
    
    subgraph "LLM Inference"
        PM --> Ollama[Local Ollama Inference]
        Architect --> Ollama
        Engineer --> Ollama
        Reviewer --> Ollama
        Reflexion --> Ollama
        DevOps --> Ollama
    end
```

## Overview
The Autonomous Software Foundry utilizes a multi-agent AI architecture orchestrated by LangGraph. It automates the software development lifecycle from natural language requirements parsing to code generation and self-healing execution.

## The LangGraph State Machine
The core workflow is governed by `AgentOrchestrator`, which manages a StateGraph representing the development lifecycle.

### State Transition Diagram

```mermaid
stateDiagram-v2
    [*] --> ProductManager: Initialize Requirements
    
    state "Human Approval Gate" as Approval1
    ProductManager --> Approval1: Generate PRD
    Approval1 --> Architect: Approved
    Approval1 --> ProductManager: Rejected/Revise
    
    state "Human Approval Gate" as Approval2
    Architect --> Approval2: Generate Architecture
    Approval2 --> Engineer: Approved
    Approval2 --> Architect: Rejected/Revise
    
    Engineer --> CodeReview: Generate Code
    
    CodeReview --> ReflexionEngine: Review Failed / Needs Tests
    CodeReview --> DevOps: Approved
    
    state ReflexionEngine {
        [*] --> Execute
        Execute --> Analyze: Failure
        Analyze --> Fix
        Fix --> Execute: Retry
        Execute --> [*]: Success / Escalate
    }
    
    ReflexionEngine --> Engineer: Fix Applied
    DevOps --> [*]: Project Deployed
```

### Agent Workflow
1. **Product Manager Agent**: Parses user requirements and generates a detailed Product Requirements Document (PRD).
2. **Architect Agent**: Designs the system architecture, tech stack, and database schema based on the PRD.
3. **Engineering Agent**: Generates the actual source code and project scaffolding.
4. **Code Review Agent**: Reviews the generated code for quality, security vulnerabilities, and adherence to standards.
5. **Reflexion Engine**: Executes the generated code in an isolated Docker sandbox. If errors occur, it analyzes the stack traces and feeds corrections back into the loop (Execute -> Analyze -> Fix -> Retry -> Escalate).
6. **DevOps Agent**: Handles final cloud provisioning and deployment configuration.

## Data Persistence & Infrastructure

```mermaid
erDiagram
    PROJECT ||--o{ AGENT_ARTIFACT : generates
    PROJECT ||--o{ APPROVAL_WORKFLOW : requires
    PROJECT {
        string id PK
        string name
        string status
        jsonb metadata
    }
    AGENT_ARTIFACT {
        string id PK
        string project_id FK
        string agent_type
        jsonb content
    }
    APPROVAL_WORKFLOW {
        string id PK
        string project_id FK
        string state
    }
```

- **PostgreSQL**: Stores relational data such as project metadata, agent artifacts, and approval workflows.
- **Redis**: Serves as a message broker for Celery background tasks and as a caching layer.
- **Neo4j**: A Knowledge Graph for semantic code understanding and persistent project memory.
- **Ollama**: The primary LLM inference engine, running locally to serve Qwen2.5-Coder models for all agent reasoning and code generation tasks.

## Human-in-the-Loop Capabilities
The architecture supports pause and resume execution, as well as explicit approval gates. This allows a human developer to intercept the workflow—for example, waiting for human review of the PRD or Architecture artifacts before proceeding to the code generation phase.
