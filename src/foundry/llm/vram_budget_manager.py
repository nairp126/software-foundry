"""VRAM Budget Manager for hardware-aware concurrency control."""

import asyncio
import logging
import time
import os
import json
import re
import heapq
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from contextlib import asynccontextmanager
from foundry.config import settings

logger = logging.getLogger(__name__)

@dataclass
class GPUDevice:
    index: int
    name: str
    total_vram_mb: int
    free_vram_mb: int

@dataclass
class InferenceMetrics:
    timestamp: str
    model_name: str
    provider: str
    agent_name: str
    priority: int
    wait_ms: float
    vram_before_mb: int
    vram_after_mb: int
    active_slots: int
    concurrency_limit: int

class AdaptivePrioritySemaphore:
    """A priority-aware, resizable async semaphore."""
    
    def __init__(self, initial_limit: int = 1):
        self._limit = max(1, initial_limit)
        self._active = 0
        self._condition = asyncio.Condition()
        self._wait_queue: List[Tuple[int, int, asyncio.Future]] = []  # (priority, seq, future)
        self._seq = 0

    async def acquire(self, priority: int = 5) -> float:
        """Acquire a slot. Returns wait time in ms."""
        start_time = time.time()
        
        async with self._condition:
            # If we have capacity and no one else is waiting, proceed
            if self._active < self._limit and not self._wait_queue:
                self._active += 1
                return 0.0
            
            # Create a future to wait on
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self._seq += 1
            heapq.heappush(self._wait_queue, [priority, self._seq, future, start_time]) # Using list to allow in-place modification
            
            # Notify everyone to re-check their status if needed
            self._condition.notify_all()
        
        # Task for anti-starvation: dynamic priority escalation
        async def escalate_priority():
            await asyncio.sleep(2.0) # Escalation threshold
            if not future.done():
                async with self._condition:
                    for item in self._wait_queue:
                        if item[2] is future:
                            item[0] = max(1, item[0] - 1) # Boost priority (lower is better)
                            heapq.heapify(self._wait_queue)
                            logger.info(f"Priority escalated for waiting agent (New Priority: {item[0]})")
                            break
        
        escalation_task = loop.create_task(escalate_priority())
            
        try:
            await future
            return (time.time() - start_time) * 1000
        except asyncio.CancelledError:
            async with self._condition:
                self._wait_queue = [item for item in self._wait_queue if item[2] is not future]
                heapq.heapify(self._wait_queue)
            raise
        finally:
            if not escalation_task.done():
                escalation_task.cancel()

    async def release(self):
        """Release a slot, wake highest-priority waiter."""
        async with self._condition:
            self._active -= 1
            self._wake_next()

    def _wake_next(self):
        """Helper to wake the next eligible waiter."""
        while self._wait_queue and self._active < self._limit:
            priority, seq, future, start_time = heapq.heappop(self._wait_queue)
            if not future.done():
                self._active += 1
                future.set_result(None)
                break

    def set_limit(self, new_limit: int):
        """Dynamically resize the limit."""
        self._limit = max(1, new_limit)
        # If limit increased, we might be able to wake more waiters
        asyncio.create_task(self._check_capacity())

    async def _check_capacity(self):
        async with self._condition:
            self._wake_next()

    @property
    def active_count(self) -> int:
        return self._active

    @property
    def queue_depth(self) -> int:
        return len(self._wait_queue)

class VRAMBudgetManager:
    """Hardware-aware VRAM governor for LLM inference."""
    
    _instance = None

    # Component 2: Model size lookup (GB)
    MODEL_VRAM_TABLE = {
        "0.5b": 0.8,
        "1.5b": 2.1,
        "3b": 3.5,
        "7b": 7.4,
        "8b": 8.5,
        "13b": 13.0,
        "14b": 14.5,
        "32b": 26.0,
        "70b": 45.0,
    }

    AGENT_PRIORITIES = {
        "Engineer": 1,
        "Reflexion": 2,
        "CodeReview": 3,
        "Architect": 4,
        "DevOps": 4,
        "ProductManager": 5,
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = None):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.model_name = model_name or settings.ollama_model_name
        self.devices: List[GPUDevice] = self._query_all_gpus()
        self.model_vram_gb = self._estimate_model_vram(self.model_name)
        self.concurrency_limit = self._compute_limit()
        self._semaphore = AdaptivePrioritySemaphore(self.concurrency_limit)
        self._metrics: List[InferenceMetrics] = []
        self._vram_history: List[Tuple[float, int]] = []
        
        logger.info(f"VRAM Manager initialized. Model: {self.model_name}, Limit: {self.concurrency_limit}, VRAM Est: {self.model_vram_gb}GB")

    def _query_all_gpus(self) -> List[GPUDevice]:
        """Component 1: Runtime VRAM Query."""
        try:
            import pynvml
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            devices = []
            for i in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                name = pynvml.nvmlDeviceGetName(handle)
                # handle might be bytes in some versions, decode if needed
                if isinstance(name, bytes):
                    name = name.decode('utf-8')
                devices.append(GPUDevice(i, name, info.total // 1048576, info.free // 1048576))
            pynvml.nvmlShutdown()
            return devices
        except Exception as e:
            # Graceful fallback for non-NVIDIA or missing pynvml
            return []

    def _get_current_free_vram_mb(self) -> int:
        devices = self._query_all_gpus()
        if not devices:
            return 0
        return sum(d.free_vram_mb for d in devices)

    def _estimate_model_vram(self, model_name: str) -> float:
        """Component 2: Model Size Estimator."""
        # Look for patterns like 7b, 1.5b, 70b in the name
        match = re.search(r'(\d+(?:\.\d+)?)[bB]', model_name)
        if match:
            size_str = match.group(1).lower() + "b"
            if size_str in self.MODEL_VRAM_TABLE:
                return self.MODEL_VRAM_TABLE[size_str]
        
        # Fallback for unknown models
        logger.warning(f"Unknown model size for {model_name}, using 4.0GB fallback.")
        return 4.0

    def _compute_limit(self) -> int:
        """Component 3: Concurrency Derivation Formula."""
        if not self.devices:
            return 1  # CPU fallback
        
        total_free_gb = sum(d.free_vram_mb for d in self.devices) / 1024
        # Apply derivation formula
        raw_limit = int(total_free_gb / (self.model_vram_gb * settings.vram_context_overhead_factor))
        
        # Clamp between 1 and max
        return max(1, min(raw_limit, settings.max_concurrent_agents))

    def recalibrate(self):
        """Component 5: Adaptive Runtime Recalibration."""
        self.devices = self._query_all_gpus()
        new_limit = self._compute_limit()
        if new_limit != self.concurrency_limit:
            logger.info(f"VRAM recalibration: {self.concurrency_limit} -> {new_limit} slots (Free VRAM: {sum(d.free_vram_mb for d in self.devices)}MB)")
            self.concurrency_limit = new_limit
            self._semaphore.set_limit(new_limit)

    def _check_oom_risk(self):
        """Component 7: OOM Prediction & Throttling."""
        if len(self._vram_history) < 3:
            return
            
        recent = self._vram_history[-5:]
        # Calculate slope: MB change per inference
        slope = (recent[-1][1] - recent[0][1]) / (len(recent) - 1)
        
        if slope < -100:  # Losing more than 100MB per call on average
            projected_vram = recent[-1][1] + (slope * 3)
            if projected_vram < 500:  # Risk of hitting < 500MB
                new_limit = max(1, self.concurrency_limit - 1)
                if new_limit < self.concurrency_limit:
                    logger.warning(f"OOM risk detected (slope: {slope:.1f}MB/call). Throttling concurrency: {self.concurrency_limit} -> {new_limit}")
                    self.concurrency_limit = new_limit
                    self._semaphore.set_limit(new_limit)

    @asynccontextmanager
    async def acquire_slot(self, agent_name: str = "unknown", provider: str = "ollama", context_size: int = 0):
        """Component 6: Agent Priority Scheduling with Context Awareness."""
        priority = self.AGENT_PRIORITIES.get(agent_name, 5)
        
        # Component 8: Context-Length Awareness
        # More realistic: ~64MB per 1K tokens for a 7B model (rule of thumb for GQA)
        context_overhead_gb = (context_size / 1000.0) * 0.064
        effective_model_vram = self.model_vram_gb + context_overhead_gb
        
        vram_before = self._get_current_free_vram_mb()
        
        # Check if we should even try
        if effective_model_vram > (vram_before / 1024.0):
             logger.warning(f"OOM Prevention: Estimated overhead ({effective_model_vram:.1f}GB) exceeds free VRAM ({vram_before/1024.0:.1f}GB). Throttling.")
             # We still try to acquire, but this helps logging
        
        wait_ms = await self._semaphore.acquire(priority)
        
        try:
            yield
        finally:
            await self._semaphore.release()
            vram_after = self._get_current_free_vram_mb()
            
            # Record for OOM tracking
            self._vram_history.append((time.time(), vram_after))
            if len(self._vram_history) > 20:
                self._vram_history.pop(0)
            
            # Component 4: Runtime Metrics
            metric = InferenceMetrics(
                timestamp=datetime.utcnow().isoformat(),
                model_name=self.model_name,
                provider=provider,
                agent_name=agent_name,
                priority=priority,
                wait_ms=wait_ms,
                vram_before_mb=vram_before,
                vram_after_mb=vram_after,
                active_slots=self._semaphore.active_count,
                concurrency_limit=self.concurrency_limit
            )
            self._metrics.append(metric)
            
            # Trigger recalibration and OOM check after each call
            self.recalibrate()
            self._check_oom_risk()

    def flush_metrics(self, project_id: str):
        """Write collected metrics to JSON report."""
        if not self._metrics:
            return
            
        report_dir = os.path.join(settings.generated_projects_path, project_id, "logs")
        os.makedirs(report_dir, exist_ok=True)
        
        report_path = os.path.join(report_dir, f"vram_metrics_{int(time.time())}.json")
        
        report_data = {
            "project_id": project_id,
            "metrics": [asdict(m) for m in self._metrics]
        }
        
        try:
            with open(report_path, "w") as f:
                json.dump(report_data, f, indent=2)
            logger.info(f"VRAM metrics flushed to: {report_path}")
            # Clear metrics after flush to avoid duplicates in future flushes if same process continues
            self._metrics = []
        except Exception as e:
            logger.error(f"Failed to flush VRAM metrics: {e}")

# Module-level singleton
vram_manager = VRAMBudgetManager()
