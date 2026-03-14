from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import uuid
from foundry.config import settings

class AgentType(str, Enum):
    PRODUCT_MANAGER = "product_manager"
    ARCHITECT = "architect"
    ENGINEER = "engineer"
    DEVOPS = "devops"
    CODE_REVIEW = "code_review"
    REFLEXION = "reflexion"

class MessageType(str, Enum):
    TASK = "task"
    RESPONSE = "response"
    ERROR = "error"
    NOTIFICATION = "notification"

class AgentMessage(BaseModel):
    """Protocol for communication between agents."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: AgentType
    recipient: AgentType
    message_type: MessageType
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None

class AgentState(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    ERROR = "error"
    TERMINATED = "terminated"

class Agent(ABC):
    """Base class for all specialized agents."""
    
    def __init__(self, agent_type: AgentType, model_name: Optional[str] = None):
        self.agent_type = agent_type
        self.model_name = model_name or settings.ollama_model_name
        self.state = AgentState.IDLE
        self.memory: List[AgentMessage] = []
        
    @abstractmethod
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process an incoming message and optionally return a response."""
        pass
    
    def update_state(self, new_state: AgentState):
        """Update the agent's internal state."""
        self.state = new_state
        # In a real implementation, this might emit an event or update a DB
        
    def add_to_memory(self, message: AgentMessage):
        """Add a message to the agent's memory."""
        self.memory.append(message)
        
    async def send_message(self, recipient: AgentType, message_type: MessageType, payload: Dict[str, Any], correlation_id: Optional[str] = None) -> AgentMessage:
        """Create a message to be sent to another agent."""
        return AgentMessage(
            sender=self.agent_type,
            recipient=recipient,
            message_type=message_type,
            payload=payload,
            correlation_id=correlation_id
        )
