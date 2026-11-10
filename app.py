"""
app.py - FastAPI application for SLI-X (Smart Reliability Intelligence).

Simulates an e-commerce request pipeline:
User Request -> API Processing -> Database Operation -> Payment Operation -> Response

Instruments all stages with microsecond-precision timers, logs telemetry, calculates SLIs,
and exposes intelligent diagnostic endpoints alongside a modern real-time dashboard.
"""
import os
import time
import uuid
import random
import threading
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

import database
from metrics import metrics_collector, RequestRecord
from diagnostic_engine import diagnostic_engine

# Current Demo Fault Injection Mode: "normal", "slow_database", "slow_payment"
CURRENT_DEMO_MODE = "normal"
DEMO_MODE_LOCK = threading.Lock()

# Traffic generator state
TRAFFIC_GENERATOR_RUNNING = False
TRAFFIC_GENERATOR_THREAD: Optional[threading.Thread] = None


def get_current_demo_mode() -> str:
    with DEMO_MODE_LOCK:
        return CURRENT_DEMO_MODE


def set_current_demo_mode(mode: str):
    global CURRENT_DEMO_MODE
    valid_modes = {"normal", "slow_database", "slow_payment"}
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Choose from: {valid_modes}")
    with DEMO_MODE_LOCK:
        CURRENT_DEMO_MODE = mode


# Request schemas
class DemoModeRequest(BaseModel):
    mode: str


class CheckoutRequest(BaseModel):
    sku: Optional[str] = "SKU-PRO-LAPTOP"
    quantity: Optional[int] = 1
    customer_id: Optional[str] = "cust_alpha_92"
    simulate_failure: Optional[bool] = False


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database and seed baseline records
    database.init_db()
    seed_baseline_traffic()
    yield
    # Shutdown: stop traffic generator if running
    global TRAFFIC_GENERATOR_RUNNING
    TRAFFIC_GENERATOR_RUNNING = False


app = FastAPI(
    title="SLI-X - Smart Reliability Intelligence",
    description="Application Performance & SLI Diagnostics Engine",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for cross-origin local access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def process_ecommerce_request(
    sku: str = "SKU-PRO-LAPTOP",
    quantity: int = 1,
    customer_id: str = "cust_alpha_92",
    simulate_failure: bool = False
) -> Dict[str, Any]:
    """
    Executes the instrumented e-commerce request pipeline:
    User Request -> API Processing -> Database Operation -> Payment Operation -> Response
    """
    request_id = f"req-{uuid.uuid4().hex[:10]}"
    req_start = time.perf_counter()
    mode = get_current_demo_mode()

    success = True
    error_message: Optional[str] = None

    # ---------------------------------------------------------
    # STAGE 1: API Processing (auth, validation, serialization)
    # ---------------------------------------------------------
    api_start = time.perf_counter()
    # Fast in-memory API verification (typically 5ms - 15ms)
    time.sleep(random.uniform(0.006, 0.015))
    api_time_ms = (time.perf_counter() - api_start) * 1000.0

    # ---------------------------------------------------------
    # STAGE 2: Database Operation (inventory read & order write)
    # ---------------------------------------------------------
    db_start = time.perf_counter()
    try:
        # FAULT INJECTION: Slow Database Scenario (~1.5s delay)
        if mode == "slow_database":
            # Real artificial wait simulating locked tables / unindexed full table scans
            time.sleep(random.uniform(1.45, 1.60))

        # Real SQLite execution
        database.execute_ecommerce_db_operation(
            order_id=request_id,
            sku=sku,
            quantity=quantity,
            amount=1899.99 * quantity
        )
    except Exception as e:
        success = False
        error_message = f"Database Error: {str(e)}"
    db_time_ms = (time.perf_counter() - db_start) * 1000.0

    # ---------------------------------------------------------
    # STAGE 3: Payment Operation (gateway authorization)
    # ---------------------------------------------------------
    payment_start = time.perf_counter()
    try:
        # FAULT INJECTION: Slow Payment Scenario (~1.5s delay)
        if mode == "slow_payment":
            # Real artificial wait simulating external payment gateway degradation
            time.sleep(random.uniform(1.45, 1.60))
        else:
            # Normal payment processing (typically 10ms - 25ms)
            time.sleep(random.uniform(0.010, 0.025))

        if simulate_failure:
            success = False
            error_message = "Payment Gateway Authorization Rejected (502 Gateway Error)"
    except Exception as e:
        success = False
        error_message = f"Payment Error: {str(e)}"
    payment_time_ms = (time.perf_counter() - payment_start) * 1000.0

    # ---------------------------------------------------------
    # STAGE 4: Final Latency Calculation & Telemetry Ingestion
    # ---------------------------------------------------------
    total_latency_ms = (time.perf_counter() - req_start) * 1000.0
    now_ts = time.time()

    record = RequestRecord(
        request_id=request_id,
        timestamp=now_ts,
        total_latency_ms=total_latency_ms,
        api_time_ms=api_time_ms,
        db_time_ms=db_time_ms,
        payment_time_ms=payment_time_ms,
        success=success,
        error_message=error_message,
        demo_mode=mode
    )

    # Ingest into in-memory rolling buffer
    metrics_collector.record_request(record)

    # Persist into SQLite telemetry table
    database.record_request_telemetry(
        request_id=request_id,
        timestamp=now_ts,
        total_latency_ms=total_latency_ms,
        api_time_ms=api_time_ms,
        db_time_ms=db_time_ms,
        payment_time_ms=payment_time_ms,
        success=success,
        error_message=error_message,
        demo_mode=mode
    )

    return {
        "request_id": request_id,
        "success": success,
        "error_message": error_message,
        "mode": mode,
        "latency_ms": {
            "total": round(total_latency_ms, 2),
            "api_processing": round(api_time_ms, 2),
            "database_operation": round(db_time_ms, 2),
            "payment_operation": round(payment_time_ms, 2)
        }
    }


def seed_baseline_traffic(count: int = 15):
    """Generates baseline healthy traffic instantly without blocking sleep."""
    now = time.time()
    for i in range(count):
        req_id = f"req-seed-{uuid.uuid4().hex[:8]}"
        api_t = round(random.uniform(6.0, 14.0), 2)
        db_t = round(random.uniform(8.0, 20.0), 2)
        pay_t = round(random.uniform(10.0, 22.0), 2)
        tot_t = round(api_t + db_t + pay_t, 2)
        ts = now - (count - i) * 2.0
        record = RequestRecord(
            request_id=req_id,
            timestamp=ts,
            total_latency_ms=tot_t,
            api_time_ms=api_t,
            db_time_ms=db_t,
            payment_time_ms=pay_t,
            success=True,
            error_message=None,
            demo_mode="normal"
        )
        metrics_collector.record_request(record)
        database.record_request_telemetry(
            request_id=req_id,
            timestamp=ts,
            total_latency_ms=tot_t,
            api_time_ms=api_t,
            db_time_ms=db_t,
            payment_time_ms=pay_t,
            success=True,
            error_message=None,
            demo_mode="normal"
        )


def traffic_generator_worker():
    """Background worker that continuously sends requests to keep telemetry active."""
    global TRAFFIC_GENERATOR_RUNNING
    while TRAFFIC_GENERATOR_RUNNING:
        try:
            process_ecommerce_request()
        except Exception:
            pass
        time.sleep(1.2)


# ==========================================
# HTTP ENDPOINTS
# ==========================================

@app.get("/", response_class=HTMLResponse)
def serve_dashboard(request: Request):
    """Serves the SLI-X interactive monitoring dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health_check():
    """Simple service health probe."""
    return {
        "status": "UP",
        "service": "SLI-X Smart Reliability Intelligence",
        "timestamp": time.time(),
        "active_mode": get_current_demo_mode()
    }


@app.get("/api/metrics")
def get_metrics():
    """
    Returns rolling SLI calculations, SLO target compliance,
    and actual host CPU & memory infrastructure metrics.
    """
    snapshot = metrics_collector.get_full_telemetry_snapshot()
    snapshot["active_demo_mode"] = get_current_demo_mode()
    snapshot["traffic_generator_active"] = TRAFFIC_GENERATOR_RUNNING
    return snapshot


@app.get("/api/diagnosis")
def get_diagnosis():
    """
    Executes the intelligent diagnostic engine against current SLIs and infrastructure metrics.
    Identifies the exact bottleneck (Database vs Payment vs CPU vs Errors)
    and explains why CPU is or is not responsible.
    """
    slis = metrics_collector.calculate_slis()
    infra = metrics_collector.get_infrastructure_metrics()

    # Collect recent errors if any
    recent_records = metrics_collector.get_recent_records(limit=20)
    recent_errors = [r["error_message"] for r in recent_records if not r["success"] and r["error_message"]]

    report = diagnostic_engine.diagnose(
        slis=slis,
        infrastructure=infra,
        recent_errors=recent_errors
    )
    report["active_demo_mode"] = get_current_demo_mode()
    return report


@app.get("/api/history")
def get_history(limit: int = 30):
    """Returns the most recent instrumented request records."""
    return {
        "requests": metrics_collector.get_recent_records(limit=limit),
        "active_mode": get_current_demo_mode()
    }


@app.post("/api/run-request")
def run_request(req: Optional[CheckoutRequest] = None):
    """
    Triggers a live e-commerce request through the full pipeline:
    API -> Database -> Payment.
    """
    if req is None:
        req = CheckoutRequest()

    result = process_ecommerce_request(
        sku=req.sku or "SKU-PRO-LAPTOP",
        quantity=req.quantity or 1,
        customer_id=req.customer_id or "cust_alpha_92",
        simulate_failure=req.simulate_failure or False
    )
    return result


@app.post("/api/demo-mode")
def set_demo_mode_endpoint(payload: DemoModeRequest):
    """
    Configures fault injection scenario:
    - 'normal': Fast baseline flow
    - 'slow_database': +1.5s delay inside database operation
    - 'slow_payment': +1.5s delay inside payment operation
    """
    try:
        set_current_demo_mode(payload.mode)
        return {
            "status": "success",
            "active_demo_mode": get_current_demo_mode(),
            "message": f"Demonstration mode switched to: {payload.mode.upper()}"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/traffic/toggle")
def toggle_traffic():
    """Starts or stops the continuous background traffic generator for live demonstrations."""
    global TRAFFIC_GENERATOR_RUNNING, TRAFFIC_GENERATOR_THREAD
    if TRAFFIC_GENERATOR_RUNNING:
        TRAFFIC_GENERATOR_RUNNING = False
        state = "stopped"
    else:
        TRAFFIC_GENERATOR_RUNNING = True
        TRAFFIC_GENERATOR_THREAD = threading.Thread(target=traffic_generator_worker, daemon=True)
        TRAFFIC_GENERATOR_THREAD.start()
        state = "started"

    return {
        "traffic_generator_running": TRAFFIC_GENERATOR_RUNNING,
        "message": f"Live background traffic generator {state}."
    }


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    """Exposes Prometheus-compatible text format metrics."""
    return metrics_collector.generate_prometheus_text()
