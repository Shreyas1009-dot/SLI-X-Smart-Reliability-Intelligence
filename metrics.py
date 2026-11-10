"""
metrics.py - SLI / SLO tracking, rolling window metrics, and psutil infrastructure measurements.
"""
import time
import math
import threading
from collections import deque
from typing import List, Dict, Any, Optional
import psutil

# SLO Targets
DEFAULT_SLO_TARGETS = {
    "availability_min_pct": 99.9,
    "p95_latency_max_ms": 200.0,
    "error_rate_max_pct": 1.0,
}


class RequestRecord:
    def __init__(
        self,
        request_id: str,
        timestamp: float,
        total_latency_ms: float,
        api_time_ms: float,
        db_time_ms: float,
        payment_time_ms: float,
        success: bool,
        error_message: Optional[str] = None,
        demo_mode: str = "normal",
    ):
        self.request_id = request_id
        self.timestamp = timestamp
        self.total_latency_ms = total_latency_ms
        self.api_time_ms = api_time_ms
        self.db_time_ms = db_time_ms
        self.payment_time_ms = payment_time_ms
        self.success = success
        self.error_message = error_message
        self.demo_mode = demo_mode

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "api_time_ms": round(self.api_time_ms, 2),
            "db_time_ms": round(self.db_time_ms, 2),
            "payment_time_ms": round(self.payment_time_ms, 2),
            "success": self.success,
            "error_message": self.error_message,
            "demo_mode": self.demo_mode,
        }


class MetricsCollector:
    def __init__(self, window_size: int = 100, window_duration_sec: float = 60.0):
        self.window_size = window_size
        self.window_duration_sec = window_duration_sec
        self.records: deque = deque(maxlen=window_size)
        self.lock = threading.Lock()
        self.slo_targets = dict(DEFAULT_SLO_TARGETS)

        # Track total lifetime requests
        self.total_lifetime_requests = 0
        self.successful_lifetime_requests = 0
        self.failed_lifetime_requests = 0

        # Initialize psutil CPU reading
        psutil.cpu_percent(interval=None)

    def record_request(self, record: RequestRecord):
        with self.lock:
            self.records.append(record)
            self.total_lifetime_requests += 1
            if record.success:
                self.successful_lifetime_requests += 1
            else:
                self.failed_lifetime_requests += 1

    def get_recent_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.lock:
            # Most recent first
            recent = list(self.records)[-limit:]
            recent.reverse()
            return [r.to_dict() for r in recent]

    def get_infrastructure_metrics(self) -> Dict[str, Any]:
        """Measures real system CPU and memory using psutil."""
        try:
            # Non-blocking CPU measurement
            cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            mem_pct = mem.percent
            mem_used_mb = round(mem.used / (1024 * 1024), 1)
            mem_total_mb = round(mem.total / (1024 * 1024), 1)
        except Exception as e:
            cpu_pct = 0.0
            mem_pct = 0.0
            mem_used_mb = 0.0
            mem_total_mb = 0.0

        return {
            "cpu_usage_pct": round(cpu_pct, 1),
            "memory_usage_pct": round(mem_pct, 1),
            "memory_used_mb": mem_used_mb,
            "memory_total_mb": mem_total_mb,
            "note": "Supporting infrastructure metrics. CPU/RAM are not SLIs."
        }

    def calculate_slis(self) -> Dict[str, Any]:
        """
        Calculates SLIs over the active rolling window:
        - Availability (%): successful / total * 100
        - Average Latency (ms)
        - P95 Latency (ms): 95th percentile
        - Error Rate (%): failed / total * 100
        - Requests Per Second (RPS)
        - Request stage breakdown (API, DB, Payment)
        """
        now = time.time()
        with self.lock:
            # Filter window to recent duration or window_size
            recent = [
                r for r in self.records 
                if (now - r.timestamp) <= self.window_duration_sec
            ]
            if not recent and self.records:
                # If traffic was paused, use the existing rolling buffer items
                recent = list(self.records)

        total_count = len(recent)

        if total_count == 0:
            return {
                "sample_count": 0,
                "availability_pct": 100.0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "error_rate_pct": 0.0,
                "requests_per_second": 0.0,
                "breakdown_ms": {
                    "api_time_ms": 0.0,
                    "db_time_ms": 0.0,
                    "payment_time_ms": 0.0,
                    "total_latency_ms": 0.0,
                },
                "breakdown_pct": {
                    "api_pct": 0.0,
                    "db_pct": 0.0,
                    "payment_pct": 0.0,
                },
                "slo_compliance": {
                    "availability_compliant": True,
                    "p95_latency_compliant": True,
                    "error_rate_compliant": True,
                    "overall_healthy": True,
                },
                "slo_targets": self.slo_targets,
            }

        successful_count = sum(1 for r in recent if r.success)
        failed_count = total_count - successful_count

        availability_pct = round((successful_count / total_count) * 100.0, 2)
        error_rate_pct = round((failed_count / total_count) * 100.0, 2)

        latencies = sorted(r.total_latency_ms for r in recent)
        avg_latency = round(sum(latencies) / total_count, 2)

        def percentile(values: List[float], p: float) -> float:
            if not values:
                return 0.0
            idx = int(math.ceil((p / 100.0) * len(values))) - 1
            idx = max(0, min(idx, len(values) - 1))
            return round(values[idx], 2)

        p50_latency = percentile(latencies, 50)
        p95_latency = percentile(latencies, 95)
        p99_latency = percentile(latencies, 99)

        # Calculate RPS based on time span of window
        time_span = max(recent[-1].timestamp - recent[0].timestamp, 1.0)
        rps = round(total_count / time_span, 2) if total_count > 1 else 1.0

        # Operation timing breakdowns (average ms across window)
        avg_api = round(sum(r.api_time_ms for r in recent) / total_count, 2)
        avg_db = round(sum(r.db_time_ms for r in recent) / total_count, 2)
        avg_payment = round(sum(r.payment_time_ms for r in recent) / total_count, 2)
        total_breakdown = avg_api + avg_db + avg_payment
        if total_breakdown > 0:
            api_pct = round((avg_api / total_breakdown) * 100.0, 1)
            db_pct = round((avg_db / total_breakdown) * 100.0, 1)
            payment_pct = round((avg_payment / total_breakdown) * 100.0, 1)
        else:
            api_pct, db_pct, payment_pct = 0.0, 0.0, 0.0

        # SLO Compliance checks
        avail_ok = availability_pct >= self.slo_targets["availability_min_pct"]
        p95_ok = p95_latency <= self.slo_targets["p95_latency_max_ms"]
        err_ok = error_rate_pct <= self.slo_targets["error_rate_max_pct"]
        overall_healthy = avail_ok and p95_ok and err_ok

        return {
            "sample_count": total_count,
            "availability_pct": availability_pct,
            "avg_latency_ms": avg_latency,
            "p50_latency_ms": p50_latency,
            "p95_latency_ms": p95_latency,
            "p99_latency_ms": p99_latency,
            "error_rate_pct": error_rate_pct,
            "requests_per_second": rps,
            "breakdown_ms": {
                "api_time_ms": avg_api,
                "db_time_ms": avg_db,
                "payment_time_ms": avg_payment,
                "total_latency_ms": avg_latency,
            },
            "breakdown_pct": {
                "api_pct": api_pct,
                "db_pct": db_pct,
                "payment_pct": payment_pct,
            },
            "slo_compliance": {
                "availability_compliant": avail_ok,
                "p95_latency_compliant": p95_ok,
                "error_rate_compliant": err_ok,
                "overall_healthy": overall_healthy,
            },
            "slo_targets": self.slo_targets,
        }

    def get_full_telemetry_snapshot(self) -> Dict[str, Any]:
        """Combines SLIs and psutil infrastructure measurements."""
        slis = self.calculate_slis()
        infra = self.get_infrastructure_metrics()
        return {
            "slis": slis,
            "infrastructure": infra,
            "timestamp": time.time(),
        }

    def generate_prometheus_text(self) -> str:
        """Exposes SLIs and infrastructure metrics in Prometheus text format."""
        snapshot = self.get_full_telemetry_snapshot()
        slis = snapshot["slis"]
        infra = snapshot["infrastructure"]

        lines = [
            "# HELP slix_availability_percent Current rolling availability percentage",
            "# TYPE slix_availability_percent gauge",
            f"slix_availability_percent {slis['availability_pct']}",
            "",
            "# HELP slix_avg_latency_ms Current rolling average latency in milliseconds",
            "# TYPE slix_avg_latency_ms gauge",
            f"slix_avg_latency_ms {slis['avg_latency_ms']}",
            "",
            "# HELP slix_p95_latency_ms Current rolling 95th percentile latency in milliseconds",
            "# TYPE slix_p95_latency_ms gauge",
            f"slix_p95_latency_ms {slis['p95_latency_ms']}",
            "",
            "# HELP slix_error_rate_percent Current rolling error rate percentage",
            "# TYPE slix_error_rate_percent gauge",
            f"slix_error_rate_percent {slis['error_rate_pct']}",
            "",
            "# HELP slix_requests_per_second Current requests per second",
            "# TYPE slix_requests_per_second gauge",
            f"slix_requests_per_second {slis['requests_per_second']}",
            "",
            "# HELP slix_api_time_ms Average API processing time in milliseconds",
            "# TYPE slix_api_time_ms gauge",
            f"slix_api_time_ms {slis['breakdown_ms']['api_time_ms']}",
            "",
            "# HELP slix_db_time_ms Average database operation time in milliseconds",
            "# TYPE slix_db_time_ms gauge",
            f"slix_db_time_ms {slis['breakdown_ms']['db_time_ms']}",
            "",
            "# HELP slix_payment_time_ms Average payment operation time in milliseconds",
            "# TYPE slix_payment_time_ms gauge",
            f"slix_payment_time_ms {slis['breakdown_ms']['payment_time_ms']}",
            "",
            "# HELP slix_infra_cpu_percent Host CPU utilization percent (infrastructure metric)",
            "# TYPE slix_infra_cpu_percent gauge",
            f"slix_infra_cpu_percent {infra['cpu_usage_pct']}",
            "",
            "# HELP slix_infra_memory_percent Host Memory utilization percent (infrastructure metric)",
            "# TYPE slix_infra_memory_percent gauge",
            f"slix_infra_memory_percent {infra['memory_usage_pct']}",
            ""
        ]
        return "\n".join(lines)


# Global singleton collector
metrics_collector = MetricsCollector()

