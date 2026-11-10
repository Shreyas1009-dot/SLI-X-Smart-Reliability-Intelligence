"""
test_diagnostics.py - Automated tests for SLI-X Diagnostic Engine & Fault Injection Scenarios.
"""
import sys
import os
import pytest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from diagnostic_engine import DiagnosticEngine
from metrics import MetricsCollector, RequestRecord, metrics_collector
from app import (
    app,
    set_current_demo_mode,
    get_current_demo_mode,
    process_ecommerce_request,
    health_check,
    get_metrics,
    get_diagnosis,
    run_request,
    set_demo_mode_endpoint,
    prometheus_metrics,
    DemoModeRequest,
    CheckoutRequest
)


@pytest.fixture
def engine():
    return DiagnosticEngine(cpu_high_threshold_pct=75.0, dominant_share_pct=45.0)


def test_rule_1_slow_database_diagnosis(engine):
    """
    Scenario:
    High latency (e.g. 1540ms vs 200ms SLO), normal CPU (18.5%),
    Database operation time accounts for most of the request (1480ms).
    SLI-X must identify Database Response Latency and explicitly rule out CPU.
    """
    slis = {
        "sample_count": 25,
        "availability_pct": 100.0,
        "avg_latency_ms": 1540.0,
        "p95_latency_ms": 1580.0,
        "error_rate_pct": 0.0,
        "breakdown_ms": {
            "api_time_ms": 15.0,
            "db_time_ms": 1480.0,
            "payment_time_ms": 45.0,
            "total_latency_ms": 1540.0,
        },
        "slo_targets": {
            "availability_min_pct": 99.9,
            "p95_latency_max_ms": 200.0,
            "error_rate_max_pct": 1.0,
        }
    }
    infrastructure = {
        "cpu_usage_pct": 18.5,
        "memory_usage_pct": 42.0,
    }

    result = engine.diagnose(slis=slis, infrastructure=infrastructure)

    assert result["status"] == "DEGRADED"
    assert result["likely_cause"] == "Likely Cause: Database Response Latency"
    assert result["affected_component"] == "Database"
    assert result["cpu_is_responsible"] is False
    assert "CPU is NOT responsible" in result["explanation"] or "CPU is normal" in result["cpu_assessment"]
    assert any("query" in fix.lower() or "index" in fix.lower() for fix in result["recommended_fix"])


def test_rule_2_slow_payment_diagnosis(engine):
    """
    Scenario:
    High latency (e.g. 1600ms), normal CPU (22%),
    Payment operation dominates (1520ms).
    """
    slis = {
        "sample_count": 20,
        "availability_pct": 100.0,
        "avg_latency_ms": 1600.0,
        "p95_latency_ms": 1620.0,
        "error_rate_pct": 0.0,
        "breakdown_ms": {
            "api_time_ms": 20.0,
            "db_time_ms": 60.0,
            "payment_time_ms": 1520.0,
            "total_latency_ms": 1600.0,
        },
        "slo_targets": {
            "availability_min_pct": 99.9,
            "p95_latency_max_ms": 200.0,
            "error_rate_max_pct": 1.0,
        }
    }
    infrastructure = {
        "cpu_usage_pct": 22.0,
        "memory_usage_pct": 40.0,
    }

    result = engine.diagnose(slis=slis, infrastructure=infrastructure)

    assert result["status"] == "DEGRADED"
    assert result["likely_cause"] == "Likely Cause: Payment Processing Delay"
    assert result["affected_component"] == "Payment Gateway"
    assert result["cpu_is_responsible"] is False
    assert any("gateway" in fix.lower() or "webhook" in fix.lower() for fix in result["recommended_fix"])


def test_rule_3_cpu_saturation_diagnosis(engine):
    """
    Scenario:
    High latency (650ms), High CPU (92%),
    Application/API processing dominates.
    SLI-X must confirm CPU is responsible.
    """
    slis = {
        "sample_count": 30,
        "availability_pct": 100.0,
        "avg_latency_ms": 650.0,
        "p95_latency_ms": 710.0,
        "error_rate_pct": 0.0,
        "breakdown_ms": {
            "api_time_ms": 580.0,
            "db_time_ms": 40.0,
            "payment_time_ms": 30.0,
            "total_latency_ms": 650.0,
        },
        "slo_targets": {
            "availability_min_pct": 99.9,
            "p95_latency_max_ms": 200.0,
            "error_rate_max_pct": 1.0,
        }
    }
    infrastructure = {
        "cpu_usage_pct": 92.4,
        "memory_usage_pct": 68.0,
    }

    result = engine.diagnose(slis=slis, infrastructure=infrastructure)

    assert result["status"] == "CRITICAL"
    assert result["likely_cause"] == "Likely Cause: CPU Saturation or Expensive Application Processing"
    assert result["affected_component"] == "Application CPU / Compute"
    assert result["cpu_is_responsible"] is True
    assert "CPU IS the bottleneck" in result["explanation"]


def test_rule_4_high_error_rate_diagnosis(engine):
    """
    Scenario:
    Error rate 8.5% breaches SLO target of < 1.0%.
    """
    slis = {
        "sample_count": 50,
        "availability_pct": 91.5,
        "avg_latency_ms": 120.0,
        "p95_latency_ms": 140.0,
        "error_rate_pct": 8.5,
        "breakdown_ms": {
            "api_time_ms": 20.0,
            "db_time_ms": 50.0,
            "payment_time_ms": 50.0,
            "total_latency_ms": 120.0,
        },
        "slo_targets": {
            "availability_min_pct": 99.9,
            "p95_latency_max_ms": 200.0,
            "error_rate_max_pct": 1.0,
        }
    }
    infrastructure = {
        "cpu_usage_pct": 25.0,
        "memory_usage_pct": 35.0,
    }

    result = engine.diagnose(
        slis=slis,
        infrastructure=infrastructure,
        recent_errors=["Payment gateway 502 bad gateway"]
    )

    assert result["status"] == "CRITICAL"
    assert "High Error Rate" in result["likely_cause"]
    assert result["affected_component"] == "Payment Gateway"


def test_rule_5_insufficient_data(engine):
    """
    Scenario:
    Zero telemetry samples recorded.
    """
    slis = {"sample_count": 0, "p95_latency_ms": 0.0, "avg_latency_ms": 0.0}
    infrastructure = {"cpu_usage_pct": 15.0, "memory_usage_pct": 30.0}

    result = engine.diagnose(slis=slis, infrastructure=infrastructure)
    assert result["status"] == "INSUFFICIENT_DATA"
    assert "Unable to confidently identify the bottleneck" in result["likely_cause"]


def test_rule_5_inconclusive_delay_split(engine):
    """
    Scenario:
    Latency is high (300ms > 200ms), but evenly divided across stages with no single dominant component.
    """
    slis = {
        "sample_count": 20,
        "availability_pct": 100.0,
        "avg_latency_ms": 300.0,
        "p95_latency_ms": 310.0,
        "error_rate_pct": 0.0,
        "breakdown_ms": {
            "api_time_ms": 100.0,
            "db_time_ms": 100.0,
            "payment_time_ms": 100.0,
            "total_latency_ms": 300.0,
        },
        "slo_targets": {
            "availability_min_pct": 99.9,
            "p95_latency_max_ms": 200.0,
            "error_rate_max_pct": 1.0,
        }
    }
    infrastructure = {"cpu_usage_pct": 20.0, "memory_usage_pct": 35.0}

    result = engine.diagnose(slis=slis, infrastructure=infrastructure)
    assert result["likely_cause"] == "Unable to confidently identify the bottleneck. More telemetry is required."


def test_healthy_baseline_within_slo(engine):
    """
    Scenario:
    All metrics well within SLO targets.
    """
    slis = {
        "sample_count": 40,
        "availability_pct": 100.0,
        "avg_latency_ms": 35.0,
        "p95_latency_ms": 48.0,
        "error_rate_pct": 0.0,
        "breakdown_ms": {
            "api_time_ms": 10.0,
            "db_time_ms": 12.0,
            "payment_time_ms": 13.0,
            "total_latency_ms": 35.0,
        },
        "slo_targets": {
            "availability_min_pct": 99.9,
            "p95_latency_max_ms": 200.0,
            "error_rate_max_pct": 1.0,
        }
    }
    infrastructure = {"cpu_usage_pct": 14.0, "memory_usage_pct": 38.0}

    result = engine.diagnose(slis=slis, infrastructure=infrastructure)
    assert result["status"] == "HEALTHY"
    assert "Operating Normally" in result["likely_cause"]


# ====================================================================
# FASTAPI ENDPOINTS & FAULT INJECTION INTEGRATION TESTS
# ====================================================================

def test_api_health_endpoint():
    data = health_check()
    assert data["status"] == "UP"
    assert "active_mode" in data


def test_api_metrics_endpoint():
    data = get_metrics()
    assert "slis" in data
    assert "infrastructure" in data
    assert "cpu_usage_pct" in data["infrastructure"]


def test_prometheus_metrics_endpoint():
    text = prometheus_metrics()
    assert "slix_availability_percent" in text
    assert "slix_p95_latency_ms" in text
    assert "slix_infra_cpu_percent" in text


def test_fault_injection_flow():
    """
    Verifies the complete fault injection lifecycle:
    1. Reset to 'normal' mode -> request is fast (< 100ms)
    2. Switch to 'slow_database' -> request latency increases (~1500ms+), DB dominates, CPU remains normal
    3. Diagnostic endpoint correctly blames Database latency, NOT CPU
    4. Switch to 'slow_payment' -> request latency increases, Payment dominates
    5. Reset to 'normal' -> request latency returns to fast baseline
    """
    # 1. Normal mode
    set_demo_mode_endpoint(DemoModeRequest(mode="normal"))
    assert get_current_demo_mode() == "normal"
    res_normal = run_request(CheckoutRequest(sku="SKU-PRO-LAPTOP", quantity=1))
    assert res_normal["latency_ms"]["total"] < 150.0

    # 2. Injected Slow Database
    set_demo_mode_endpoint(DemoModeRequest(mode="slow_database"))
    assert get_current_demo_mode() == "slow_database"
    res_slow_db = run_request(CheckoutRequest(sku="SKU-PRO-LAPTOP", quantity=1))
    assert res_slow_db["latency_ms"]["total"] >= 1400.0
    assert res_slow_db["latency_ms"]["database_operation"] >= 1400.0

    # 3. Check diagnosis after slow DB
    diag_data = get_diagnosis()
    assert diag_data["affected_component"] == "Database"
    assert "Database Response Latency" in diag_data["likely_cause"]
    assert diag_data["cpu_is_responsible"] is False

    # 4. Injected Slow Payment
    set_demo_mode_endpoint(DemoModeRequest(mode="slow_payment"))
    assert get_current_demo_mode() == "slow_payment"
    res_slow_pay = run_request(CheckoutRequest(sku="SKU-PRO-LAPTOP", quantity=1))
    assert res_slow_pay["latency_ms"]["payment_operation"] >= 1400.0

    # 5. Reset to Normal
    set_demo_mode_endpoint(DemoModeRequest(mode="normal"))
    assert get_current_demo_mode() == "normal"
    res_restored = run_request(CheckoutRequest(sku="SKU-PRO-LAPTOP", quantity=1))
    assert res_restored["latency_ms"]["total"] < 150.0
