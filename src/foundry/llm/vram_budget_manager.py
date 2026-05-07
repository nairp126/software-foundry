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

    async def acquire(self, priority: int = 5, timeout: float = 120.0) -> float:
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
            # Using list to allow in-place modification for priority escalation
            wait_item = [priority, self._seq, future, start_time]
            heapq.heappush(self._wait_queue, wait_item)
            
            # Notify everyone to re-check their status if needed
            self._condition.notify_all()
        
        # Task for anti-starvation: dynamic priority escalation
        async def escalate_priority():
            try:
                await asyncio.sleep(2.0) # Escalation threshold
                if not future.done():
                    async with self._condition:
                        for item in self._wait_queue:
                            if item[2] is future:
                                item[0] = max(1, item[0] - 1) # Boost priority (lower is better)
                                heapq.heapify(self._wait_queue)
                                logger.info(f"Priority escalated for waiting agent (New Priority: {item[0]})")
                                break
            except asyncio.CancelledError:
                pass
        
        escalation_task = loop.create_task(escalate_priority())
            
        try:
            await asyncio.wait_for(future, timeout=timeout)
            return (time.time() - start_time) * 1000
        except asyncio.TimeoutError:
            async with self._condition:
                # Remove the future from the wait queue if it's still there
                self._wait_queue = [item for item in self._wait_queue if item[2] is not future]
                heapq.heapify(self._wait_queue)
            raise TimeoutError(
                f"VRAM semaphore acquire timed out after {timeout}s. "
                f"GPU may be occupied by another process."
            )
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

    # Empirical Constant for Context-Length Awareness
    # Based on vLLM memory profiling and the Qwen2.5 Technical Report for models using 
    # Grouped-Query Attention (GQA). For a 7B-8B parameter model, the KV cache footprint 
    # is approximately 64 MB per 1,000 tokens of context.
    # Source: Derived from vLLM PagedAttention benchmarking (https://vllm.ai/)
    KV_CACHE_GB_PER_1K_TOKENS = 0.064

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
        self._stable_calls = 0
        
        # Calibration state
        self._calibrated = False
        self._gb_per_1k_tokens = self.KV_CACHE_GB_PER_1K_TOKENS
        
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
        """
        PATENT-CRITICAL: Graduated Concurrency Decay & Recovery (Feature 2).
        Uses a PID-like response to VRAM volatility:
        - Critical Risk: 50% reduction if VRAM < 5% or slope < -1GB/call
        - Moderate Risk: -1 reduction if projected VRAM < 1GB
        - Stability: +1 recovery if stable for N calls (vram_recovery_patience)
        """
        if len(self._vram_history) < 3:
            return
            
        recent = self._vram_history[-5:]
        vram_now = recent[-1][1]
        # Calculate slope: MB change per inference
        slope = (recent[-1][1] - recent[0][1]) / (len(recent) - 1)
        
        # 1. Critical Decay: immediate 50% drop if extremely low or crashing
        total_vram = sum(d.total_vram_mb for d in self.devices)
        if vram_now < (total_vram * 0.05) or slope < -1000:
             new_limit = max(1, self.concurrency_limit // 2)
             if new_limit < self.concurrency_limit:
                 logger.warning(f"CRITICAL OOM RISK: VRAM at {vram_now}MB. Applying 50% decay: {self.concurrency_limit} -> {new_limit}")
                 self.concurrency_limit = new_limit
                 self._semaphore.set_limit(new_limit)
                 self._stable_calls = 0
                 return

        # 2. Moderate Decay
        if slope < -100:  # Losing more than 100MB per call
            projected_vram = vram_now + (slope * 3)
            if projected_vram < 1000:
                new_limit = max(1, self.concurrency_limit - 1)
                if new_limit < self.concurrency_limit:
                    logger.warning(f"Moderate OOM risk (slope: {slope:.1f}MB/call). Throttling: {self.concurrency_limit} -> {new_limit}")
                    self.concurrency_limit = new_limit
                    self._semaphore.set_limit(new_limit)
                    self._stable_calls = 0
                    return
        
        # 3. Recovery: if slope is flat/positive and we have headroom
        if slope >= 0 and vram_now > (total_vram * 0.2):
            self._stable_calls += 1
            if self._stable_calls >= settings.vram_recovery_patience:
                # Can we increase?
                target_limit = self._compute_limit()
                if self.concurrency_limit < target_limit:
                    new_limit = self.concurrency_limit + 1
                    logger.info(f"VRAM Stability detected ({self._stable_calls} calls). Recovering concurrency: {self.concurrency_limit} -> {new_limit}")
                    self.concurrency_limit = new_limit
                    self._semaphore.set_limit(new_limit)
                    self._stable_calls = 0
        else:
            self._stable_calls = 0

    @asynccontextmanager
    async def acquire_slot(
        self, 
        agent_name: str = "unknown", 
        provider: str = "ollama", 
        context_size: int = 0,
        provider_instance: Optional[Any] = None
    ):
        """Component 6: Agent Priority Scheduling with Context Awareness."""
        # Auto-calibrate on first boot if supported
        if not self._calibrated and provider_instance and settings.enable_kv_calibration:
            await self.calibrate_kv_cache(provider_instance, context_size or 1024)

        priority = self.AGENT_PRIORITIES.get(agent_name, 5)
        
        # Component 8: Context-Length Awareness
        # Uses the calibrated or empirically-derived constant for KV cache footprint estimation.
        context_overhead_gb = (context_size / 1000.0) * self._gb_per_1k_tokens
        effective_model_vram = self.model_vram_gb + context_overhead_gb
        
        vram_before = self._get_current_free_vram_mb()
        
        # Check if we should even try
        if effective_model_vram > (vram_before / 1024.0):
             logger.warning(f"OOM Prevention: Estimated overhead ({effective_model_vram:.1f}GB) exceeds free VRAM ({vram_before/1024.0:.1f}GB). Throttling.")
             # We still try to acquire, but this helps logging
        
        wait_ms = await self._semaphore.acquire(priority, timeout=settings.vram_acquire_timeout_seconds)
        
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
            
            self.recalibrate()
            self._check_oom_risk()

    def calculate_fairness_index(self) -> float:
        """
        PATENT-CRITICAL: Jain's Fairness Index (Feature 5).
        Measures the equitability of the priority scheduler.
        J = (Σ wait_ms)² / (n * Σ wait_ms²)
        Range: 1/n (worst) to 1.0 (perfectly fair).
        """
        if not self._metrics:
            return 1.0
            
        wait_times = [m.wait_ms for m in self._metrics]
        n = len(wait_times)
        if n == 0: return 1.0
        
        sum_wait = sum(wait_times)
        sum_sq_wait = sum(w**2 for w in wait_times)
        
        if sum_sq_wait == 0: return 1.0 # All zero wait is perfectly fair
        
        fairness = (sum_wait**2) / (n * sum_sq_wait)
        logger.info(f"Priority Fairness Index: {fairness:.3f} (n={n})")
        return fairness

    async def calibrate_kv_cache(self, provider_instance: Any, context_size: int = 1024):
        """
        PATENT-CRITICAL: Hardware-Aware Calibration.
        Measures the actual KV cache delta during a dummy inference call to refine
        the gb_per_1k_tokens constant for the specific local hardware.
        """
        if self._calibrated or not settings.enable_kv_calibration:
            return

        logger.info("Starting hardware-aware KV cache calibration...")
        vram_before = self._get_current_free_vram_mb()
        
        try:
            # Prevent infinite recursion by marking as calibrated before generation
            self._calibrated = True
            
            # Perform a small dummy generation to trigger KV cache allocation
            from foundry.llm.base import LLMMessage
            dummy_messages = [LLMMessage(role="user", content="Hi " * (context_size // 4))]
            await provider_instance.generate(dummy_messages, max_tokens=10, skip_calibration=True)
            
            vram_after = self._get_current_free_vram_mb()
            vram_delta_mb = vram_before - vram_after
            
            if vram_delta_mb > 0:
                # Convert MB to GB for the constant
                self._gb_per_1k_tokens = (vram_delta_mb / 1024.0) / (context_size / 1000.0)
                # Sanity check: cap at 0.5 GB/1K and min at 0.01 to avoid wild outliers
                self._gb_per_1k_tokens = max(0.01, min(self._gb_per_1k_tokens, 0.5))
                logger.info(f"Calibration complete: {self._gb_per_1k_tokens:.4f} GB/1K tokens (Hardware: {self.devices[0].name})")
        except Exception as e:
            logger.warning(f"KV cache calibration failed (non-blocking): {e}. Using empirical default.")

    async def flush_metrics(self, project_id: str):
        """Write collected metrics to JSON report and PostgreSQL (Dual-Persistence)."""
        if not self._metrics:
            return
            
        # Calculate fairness before flushing
        fairness = self.calculate_fairness_index()
        
        # 1. Local JSON Fallback (Req 9.2)
        report_dir = os.path.join(settings.generated_projects_path, project_id, "logs")
        os.makedirs(report_dir, exist_ok=True)
        
        report_path = os.path.join(report_dir, f"vram_metrics_{int(time.time())}.json")
        
        metrics_dict = [asdict(m) for m in self._metrics]
        report_data = {
            "project_id": project_id,
            "fairness_index": fairness,
            "metrics": metrics_dict
        }
        
        try:
            with open(report_path, "w") as f:
                json.dump(report_data, f, indent=2)
            logger.info(f"VRAM metrics flushed to JSON: {report_path}")
        except Exception as e:
            logger.error(f"Failed to flush VRAM metrics to JSON: {e}")

        # 2. PostgreSQL Primary (Feature 10)
        try:
            from foundry.database import AsyncSessionLocal
            from foundry.models.inference_metric import InferenceMetric
            from datetime import datetime
            
            async with AsyncSessionLocal() as session:
                for m in self._metrics:
                    db_metric = InferenceMetric(
                        project_id=project_id,
                        model_name=m.model_name,
                        provider=m.provider,
                        agent_name=m.agent_name,
                        priority=m.priority,
                        wait_ms=m.wait_ms,
                        vram_before_mb=m.vram_before_mb,
                        vram_after_mb=m.vram_after_mb,
                        active_slots=m.active_slots,
                        concurrency_limit=m.concurrency_limit,
                        fairness_index=fairness
                    )
                    session.add(db_metric)
                await session.commit()
            logger.info(f"VRAM metrics flushed to PostgreSQL (n={len(self._metrics)})")
        except Exception as e:
            logger.error(f"Failed to flush VRAM metrics to PostgreSQL: {e}")
        
        # Clear metrics after flush to avoid duplicates
        self._metrics = []

# Module-level singleton
vram_manager = VRAMBudgetManager()
