from dataclasses import dataclass, field, asdict
import json
import os
import time
from typing import List, Dict, Any
from datetime import datetime
from foundry.config import settings

@dataclass
class SurgicalContextMetrics:
    file_path: str
    kg_context_tokens: int = 0
    fallback_context_tokens: int = 0
    kg_retrieval_latency_ms: float = 0.0
    ingestion_latency_ms: float = 0.0
    import_errors_detected: int = 0
    symbols_resolved: int = 0
    path_used: str = "unknown"  # "kg_surgical" or "fallback_truncation"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

class MetricsCollector:
    """Collects and flushes metrics to a JSON report for patent evidence."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.metrics: List[SurgicalContextMetrics] = []
        self.start_time = time.time()

    def add_metric(self, metric: SurgicalContextMetrics):
        self.metrics.append(metric)

    def flush(self):
        """Write metrics to a JSON file in the project directory."""
        if not self.metrics:
            return

        report_dir = os.path.join(settings.generated_projects_path, self.project_id, "logs")
        os.makedirs(report_dir, exist_ok=True)
        
        report_path = os.path.join(report_dir, f"patent_metrics_{int(time.time())}.json")
        
        report_data = {
            "project_id": self.project_id,
            "total_duration_s": time.time() - self.start_time,
            "file_metrics": [asdict(m) for m in self.metrics]
        }
        
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)
            
        return report_path
