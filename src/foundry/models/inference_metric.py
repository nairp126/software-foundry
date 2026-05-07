"""Inference metrics model for telemetry persistence."""

from sqlalchemy import Column, String, Float, Integer
from foundry.database import Base
from foundry.models.base import BaseModel

class InferenceMetric(BaseModel, Base):
    """
    PATENT-CRITICAL: Inference Telemetry Persistence.
    Stores VRAM usage, wait times, and fairness metrics for scientific auditing
    and patent-defensible claim verification.
    """
    __tablename__ = "inference_metrics"

    project_id = Column(String(255), nullable=False, index=True)
    model_name = Column(String(255), nullable=False)
    provider = Column(String(100), nullable=False)
    agent_name = Column(String(100), nullable=False)
    priority = Column(Integer, nullable=False)
    wait_ms = Column(Float, nullable=False)
    vram_before_mb = Column(Integer, nullable=False)
    vram_after_mb = Column(Integer, nullable=False)
    active_slots = Column(Integer, nullable=False)
    concurrency_limit = Column(Integer, nullable=False)
    fairness_index = Column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"<InferenceMetric {self.agent_name} wait={self.wait_ms:.1f}ms>"
