"""
diagnostic_engine.py - Core Diagnostic Engine for SLI-X.

Analyzes application request breakdown timings and infrastructure telemetry
to identify performance bottlenecks, rule out false assumptions (such as blaming CPU
when the database is lagging), and deliver actionable engineering remedies.
"""
from typing import Dict, Any, List, Optional


class DiagnosticEngine:
    """
    SLI-X Intelligent Diagnostic Engine.
    Evaluates empirical SLI metrics and infrastructure data against expert rules.
    """

    def __init__(
        self,
        cpu_high_threshold_pct: float = 75.0,
        dominant_share_pct: float = 45.0,
    ):
        self.cpu_high_threshold_pct = cpu_high_threshold_pct
        self.dominant_share_pct = dominant_share_pct

    def diagnose(
        self,
        slis: Dict[str, Any],
        infrastructure: Dict[str, Any],
        recent_errors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes diagnostic rules on current SLI metrics and system metrics.

        Rules:
        1. If application latency is high, CPU is normal, and database operation time
           is the largest portion of the request:
           -> 'Likely Cause: Database Response Latency'
        2. If application latency is high and payment operation time dominates:
           -> 'Likely Cause: Payment Processing Delay'
        3. If application latency is high, CPU is high, and application processing time dominates:
           -> 'Likely Cause: CPU Saturation or Expensive Application Processing'
        4. If the error rate is high:
           -> Report the affected operation and error condition.
        5. If evidence is insufficient:
           -> 'Unable to confidently identify the bottleneck. More telemetry is required.'
        """
        sample_count = slis.get("sample_count", 0)
        p95_latency = slis.get("p95_latency_ms", 0.0)
        avg_latency = slis.get("avg_latency_ms", 0.0)
        error_rate = slis.get("error_rate_pct", 0.0)
        slo_targets = slis.get("slo_targets", {})
        p95_target = slo_targets.get("p95_latency_max_ms", 200.0)
        error_target = slo_targets.get("error_rate_max_pct", 1.0)

        breakdown_ms = slis.get("breakdown_ms", {})
        api_time = breakdown_ms.get("api_time_ms", 0.0)
        db_time = breakdown_ms.get("db_time_ms", 0.0)
        payment_time = breakdown_ms.get("payment_time_ms", 0.0)
        total_time = breakdown_ms.get("total_latency_ms", avg_latency)

        cpu_usage = infrastructure.get("cpu_usage_pct", 0.0)
        memory_usage = infrastructure.get("memory_usage_pct", 0.0)

        # Baseline check: insufficient sample data
        if sample_count == 0:
            return self._format_result(
                status="INSUFFICIENT_DATA",
                likely_cause="Unable to confidently identify the bottleneck. More telemetry is required.",
                affected_component="Unknown",
                explanation="No telemetry records are available in the current evaluation window. Generate traffic to enable diagnostic analysis.",
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                cpu_is_responsible=False,
                recommended_fix=[
                    "Send test requests or start the live traffic generator to collect telemetry.",
                    "Verify monitoring hooks and telemetry ingestion endpoints are active."
                ],
                timings=breakdown_ms,
                p95_latency=p95_latency,
                avg_latency=avg_latency,
            )

        # Calculate stage shares
        stage_sum = api_time + db_time + payment_time
        if stage_sum > 0:
            api_share = (api_time / stage_sum) * 100.0
            db_share = (db_time / stage_sum) * 100.0
            payment_share = (payment_time / stage_sum) * 100.0
        else:
            api_share, db_share, payment_share = 0.0, 0.0, 0.0

        latency_high = (p95_latency > p95_target) or (avg_latency > p95_target)
        cpu_is_high = cpu_usage >= self.cpu_high_threshold_pct
        error_is_high = error_rate > error_target

        # RULE 4: High Error Rate
        if error_is_high:
            affected_op = "API Gateway / Request Processing"
            if recent_errors:
                err_sample = recent_errors[0]
                if "db" in err_sample.lower() or "database" in err_sample.lower():
                    affected_op = "Database Transaction"
                elif "payment" in err_sample.lower():
                    affected_op = "Payment Gateway"
            else:
                err_sample = f"Error rate breached SLO target ({error_rate:.1f}% > {error_target:.1f}%)"

            return self._format_result(
                status="CRITICAL",
                likely_cause=f"Likely Cause: High Error Rate in {affected_op}",
                affected_component=affected_op,
                explanation=(
                    f"Application error rate is currently {error_rate:.2f}%, violating the SLO target "
                    f"of < {error_target:.1f}%. CPU utilization is at {cpu_usage:.1f}%. Failures are causing "
                    f"immediate request degradation regardless of latency."
                ),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                cpu_is_responsible=cpu_is_high,
                recommended_fix=[
                    f"Review application logs for unhandled 5xx exceptions in {affected_op}.",
                    "Implement circuit breaker and fallbacks to handle upstream/downstream errors gracefully.",
                    "Verify connectivity, schema integrity, and input validation on checkout endpoints."
                ],
                timings=breakdown_ms,
                p95_latency=p95_latency,
                avg_latency=avg_latency,
            )

        # RULE 1: Database Latency Dominates (CPU Normal)
        if latency_high and not cpu_is_high and (db_time >= api_time and db_time >= payment_time and db_share >= self.dominant_share_pct):
            return self._format_result(
                status="DEGRADED",
                likely_cause="Likely Cause: Database Response Latency",
                affected_component="Database",
                explanation=(
                    f"The application is experiencing severe latency degradation (P95: {p95_latency:.1f} ms, "
                    f"Avg: {avg_latency:.1f} ms, exceeding SLO target of {p95_target:.1f} ms). "
                    f"Telemetry decomposition reveals the Database operation consumes {db_time:.1f} ms "
                    f"({db_share:.1f}% of total request time), while API processing ({api_time:.1f} ms) "
                    f"and Payment processing ({payment_time:.1f} ms) remain negligible.\n\n"
                    f"Infrastructure analysis confirms host CPU usage is at {cpu_usage:.1f}% (normal, well below the "
                    f"{self.cpu_high_threshold_pct:.0f}% saturation limit) and Memory is {memory_usage:.1f}%. "
                    f"Therefore, CPU is NOT responsible for this slowdown. The degradation is an I/O wait / downstream "
                    f"database response issue."
                ),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                cpu_is_responsible=False,
                recommended_fix=[
                    "Check SQLite / relational database slow query logs and execution plans (EXPLAIN QUERY PLAN).",
                    "Verify appropriate index coverage on queried tables (`orders`, `inventory`).",
                    "Investigate database lock contention, transaction wait times, or connection pool limits.",
                    "Consider caching frequently read catalog data using Redis or an in-memory cache."
                ],
                timings=breakdown_ms,
                p95_latency=p95_latency,
                avg_latency=avg_latency,
            )

        # RULE 2: Payment Processing Delay (CPU Normal or Latency Dominated by Payment)
        if latency_high and (payment_time >= api_time and payment_time >= db_time and payment_share >= self.dominant_share_pct):
            return self._format_result(
                status="DEGRADED",
                likely_cause="Likely Cause: Payment Processing Delay",
                affected_component="Payment Gateway",
                explanation=(
                    f"Application response latency is elevated (P95: {p95_latency:.1f} ms, Avg: {avg_latency:.1f} ms, "
                    f"SLO target: {p95_target:.1f} ms). Telemetry metrics identify the Payment operation as the "
                    f"overwhelming bottleneck, accounting for {payment_time:.1f} ms ({payment_share:.1f}% of request time). "
                    f"API processing takes {api_time:.1f} ms and Database takes {db_time:.1f} ms.\n\n"
                    f"System CPU is at {cpu_usage:.1f}%, confirming CPU is NOT the cause. The delay originates from "
                    f"external payment provider latency or network round-trip delays."
                ),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                cpu_is_responsible=False,
                recommended_fix=[
                    "Check third-party payment gateway health, API latency, and status dashboards.",
                    "Verify HTTP client timeouts, socket keep-alive, and connection pooling for gateway requests.",
                    "Implement asynchronous payment processing with webhooks instead of blocking synchronous HTTP calls.",
                    "Add circuit breaking to avoid cascading thread starvation during payment provider outages."
                ],
                timings=breakdown_ms,
                p95_latency=p95_latency,
                avg_latency=avg_latency,
            )

        # RULE 3: CPU Saturation / Expensive Application Processing
        if latency_high and cpu_is_high and (api_time >= db_time and api_time >= payment_time and api_share >= self.dominant_share_pct):
            return self._format_result(
                status="CRITICAL",
                likely_cause="Likely Cause: CPU Saturation or Expensive Application Processing",
                affected_component="Application CPU / Compute",
                explanation=(
                    f"Application latency is elevated (P95: {p95_latency:.1f} ms), and system CPU usage has reached "
                    f"{cpu_usage:.1f}%, exceeding the saturation threshold of {self.cpu_high_threshold_pct:.0f}%. "
                    f"Internal telemetry indicates API processing is the dominant phase, consuming {api_time:.1f} ms "
                    f"({api_share:.1f}% of total time).\n\n"
                    f"In this scenario, CPU IS the bottleneck. Intensive in-process computation, serialization overhead, "
                    f"or thread contention is causing request queuing and compute starvation."
                ),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                cpu_is_responsible=True,
                recommended_fix=[
                    "Profile CPU hotspots using profiling tools (e.g. py-spy, cProfile) to identify compute-heavy loops.",
                    "Scale the application horizontally by increasing worker processes or pod instances.",
                    "Offload heavy data processing, cryptographic signing, or compression to asynchronous background workers.",
                    "Optimize data serialization/deserialization routines."
                ],
                timings=breakdown_ms,
                p95_latency=p95_latency,
                avg_latency=avg_latency,
            )

        # HEALTHY: Operating within SLO targets
        if not latency_high and not error_is_high:
            return self._format_result(
                status="HEALTHY",
                likely_cause="System Operating Normally (Within SLOs)",
                affected_component="None",
                explanation=(
                    f"All key SLIs comply with target objectives. P95 latency is {p95_latency:.1f} ms "
                    f"(Target: < {p95_target:.1f} ms), Error rate is {error_rate:.2f}% (Target: < {error_target:.1f}%), "
                    f"and Availability is {slis.get('availability_pct', 100.0):.2f}% (Target: >= {slo_targets.get('availability_min_pct', 99.9):.1f}%). "
                    f"Host CPU usage is {cpu_usage:.1f}% and Memory is {memory_usage:.1f}%. No bottleneck detected."
                ),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                cpu_is_responsible=False,
                recommended_fix=[
                    "System performance is optimal. Continue monitoring SLI trends and SLO burn rate.",
                    "Maintain alerting rules on P95 latency and error rate thresholds."
                ],
                timings=breakdown_ms,
                p95_latency=p95_latency,
                avg_latency=avg_latency,
            )

        # RULE 5: Insufficient or Inconclusive Evidence
        return self._format_result(
            status="DEGRADED",
            likely_cause="Unable to confidently identify the bottleneck. More telemetry is required.",
            affected_component="Indeterminate",
            explanation=(
                f"Latency is elevated (P95: {p95_latency:.1f} ms, SLO: {p95_target:.1f} ms), but no single stage "
                f"(API: {api_time:.1f} ms, DB: {db_time:.1f} ms, Payment: {payment_time:.1f} ms) accounts for "
                f"a dominant majority (threshold: {self.dominant_share_pct:.0f}%). CPU is at {cpu_usage:.1f}%. "
                f"The delay may be distributed across multiple micro-steps or caused by network transmission overhead. "
                f"More fine-grained spans or additional telemetry samples are required."
            ),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            cpu_is_responsible=cpu_is_high,
            recommended_fix=[
                "Instrument finer-grained sub-spans within API processing, ORM queries, and external HTTP calls.",
                "Collect additional request samples over an expanded time window.",
                "Inspect network round-trip times (RTT) and gateway proxy logs."
            ],
            timings=breakdown_ms,
            p95_latency=p95_latency,
            avg_latency=avg_latency,
        )

    def _format_result(
        self,
        status: str,
        likely_cause: str,
        affected_component: str,
        explanation: str,
        cpu_usage: float,
        memory_usage: float,
        cpu_is_responsible: bool,
        recommended_fix: List[str],
        timings: Dict[str, float],
        p95_latency: float,
        avg_latency: float,
    ) -> Dict[str, Any]:
        """Builds a standardized, evidence-backed diagnostic report."""
        cpu_reason = (
            f"CPU is high ({cpu_usage:.1f}%), indicating compute contention."
            if cpu_is_responsible
            else f"CPU is normal ({cpu_usage:.1f}%), ruling out CPU exhaustion as the root cause."
        )

        return {
            "status": status,
            "likely_cause": likely_cause,
            "affected_component": affected_component,
            "cpu_is_responsible": cpu_is_responsible,
            "cpu_assessment": cpu_reason,
            "explanation": explanation,
            "recommended_fix": recommended_fix,
            "evidence": {
                "p95_latency_ms": round(p95_latency, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "cpu_usage_pct": round(cpu_usage, 1),
                "memory_usage_pct": round(memory_usage, 1),
                "timings_ms": {
                    "api_time_ms": round(timings.get("api_time_ms", 0.0), 2),
                    "db_time_ms": round(timings.get("db_time_ms", 0.0), 2),
                    "payment_time_ms": round(timings.get("payment_time_ms", 0.0), 2),
                    "total_latency_ms": round(timings.get("total_latency_ms", avg_latency), 2),
                }
            }
        }


# Global singleton instance
diagnostic_engine = DiagnosticEngine()

