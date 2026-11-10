# SLI-X — Smart Reliability Intelligence

> **Empirical Application Performance & SLI Diagnostics Engine**  
> Diagnoses slow applications when CPU and memory are completely normal by decomposing internal request timings across API, Database, and Payment pipelines.

---

## 🎯 The Central Problem & Innovation

In modern cloud-native systems, engineers frequently face this baffling production incident:

> **"The website is painfully slow or timing out, but the CPU dashboard shows 25% utilization and RAM is at 40%. Cloud monitoring reports 'Everything is Healthy'."**

Traditional monitoring tools (CloudWatch, Datadog host agents, VM dashboards) monitor **host infrastructure metrics** (CPU, RAM, Disk I/O). When a downstream database transaction locks or a third-party payment gateway lags, CPU threads sit idle in an **I/O wait** state. As a result:
- CPU utilization stays **LOW/NORMAL**.
- Traditional alerts fail to fire.
- DevOps engineers waste hours rebooting healthy servers or guessing at compute capacity.

### SLI-X Solution:
**SLI-X** decouples **Infrastructure Metrics** from **Core Service Level Indicators (SLIs)**. It instruments every stage of the request pipeline with microsecond timers:

$$\text{User Request} \longrightarrow \text{API Processing} \longrightarrow \text{Database Operation} \longrightarrow \text{Payment Operation} \longrightarrow \text{Response}$$

When an SLO breach occurs, the **SLI-X Intelligent Diagnostic Engine** correlates real-time request stage breakdowns against host telemetry to deliver an empirical, evidence-backed root-cause diagnosis.

---

## 📐 Architecture & Key Concepts

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             SLI-X ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   HTTP Client / Browser (Port 8000)                                         │
│         │                                                                   │
│         ▼                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         FastAPI Web Server                          │   │
│   │                                                                     │   │
│   │  [Stage 1: API Processing] ──► [Stage 2: Database] ──► [Stage 3]   │   │
│   │   Auth & Payload Validation     SQLite Inventory / Orders    Payment    │   │
│   │   (5 - 15 ms)                   (10 - 25 ms normal,          Gateway    │   │
│   │                                  +1.5s injected wait)        (15-25ms)  │   │
│   └───────────────────────────────────┬─────────────────────────────────┘   │
│                                       │ Timers (time.perf_counter)          │
│                                       ▼                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       Metrics Collector Engine                      │   │
│   │   • Rolling Window (60s) SLIs: Availability, P95, Avg, Error Rate   │   │
│   │   • Host Telemetry (psutil): CPU %, Memory %                        │   │
│   │   • SQLite Telemetry Persistence (request_telemetry table)          │   │
│   │   • Prometheus /metrics Exporter                                    │   │
│   └───────────────────────────────────┬─────────────────────────────────┘   │
│                                       │ Telemetry Feeds                     │
│                                       ▼                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    Intelligent Diagnostic Engine                    │   │
│   │   • Rule 1: High Latency + Normal CPU + DB Dominates                │   │
│   │             ─► "Likely Cause: Database Response Latency"            │   │
│   │   • Rule 2: High Latency + Payment Dominates                        │   │
│   │             ─► "Likely Cause: Payment Processing Delay"             │   │
│   │   • Rule 3: High Latency + High CPU + API Dominates                 │   │
│   │             ─► "Likely Cause: CPU Saturation / Compute"             │   │
│   │   • Rule 4: High Error Rate ─► "High Error Rate in [Op]"            │   │
│   │   • Rule 5: Insufficient Evidence ─► "Telemetry Inconclusive"       │   │
│   └───────────────────────────────────┬─────────────────────────────────┘   │
│                                       │ Structured Findings                 │
│                                       ▼                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │               Dark-Theme Real-Time Live Dashboard                   │   │
│   │   • SLIs vs SLO Targets (Target: < 200ms | Actual: 1,540ms)         │   │
│   │   • Prominent Diagnosis Hero Card with CPU Ruling & Fixes           │   │
│   │   • Stacked Latency Breakdown Bar (% and ms per stage)              │   │
│   │   • Real-Time Request Stream Table with Bottleneck Flags            │   │
│   │   • One-Click Fault Injection Controls & Live Traffic Generator     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quickstart & Setup (Windows PowerShell)

### Prerequisites
- Python 3.10+ installed
- PowerShell or Terminal

### 1. Clone or Navigate to the Directory
```powershell
cd "c:\projects\Cloud native\SLI-X"
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Run Automated Tests
```powershell
pytest -v tests/test_diagnostics.py
```

### 4. Start the SLI-X Application
```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

### 5. Open the Dashboard
Navigate to:
```
http://127.0.0.1:8001
```

---

## 📡 API Endpoints Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Serves the interactive dark-theme SLI-X dashboard |
| `/health` | `GET` | Service health status and active fault injection mode |
| `/api/metrics` | `GET` | Rolling window SLIs, SLO compliance flags, and host CPU/RAM |
| `/api/diagnosis` | `GET` | Real-time intelligent diagnostic report from `diagnostic_engine.py` |
| `/api/history` | `GET` | Recent instrumented requests stream (last 30 requests) |
| `/api/run-request` | `POST` | Triggers a live e-commerce checkout request through the pipeline |
| `/api/demo-mode` | `POST` | Sets fault injection mode: `normal`, `slow_database`, `slow_payment` |
| `/api/traffic/toggle`| `POST` | Toggles the continuous background traffic generator |
| `/metrics` | `GET` | Prometheus-compatible text format metrics exporter |

---

## 🎓 Step-by-Step Live Demonstration Script for College Review

This script provides an exact 5-minute walkthrough designed to demonstrate SLI-X during a project presentation or college viva review.

### Step 1: Explain the Core Problem (30 seconds)
1. Open the dashboard at `http://127.0.0.1:8001`.
2. Point to the **Host Infrastructure Panel** (left) vs **Core SLIs Panel** (right).
3. **Say:**  
   *"In production, infrastructure metrics such as CPU and RAM do not represent user experience. A website can be completely broken while CPU sits at 15%. SLI-X separates infrastructure metrics from SLIs and diagnoses bottlenecks by instrumenting every micro-step of request execution."*

### Step 2: Normal Baseline Operation (45 seconds)
1. Verify that the mode is set to **Normal Mode**.
2. Click **Start Live Traffic**. You will see continuous requests streaming into the Recent Requests table every 1.2s.
3. Observe:
   - **Availability:** 100% (Target: $\ge$ 99.9%)
   - **P95 Latency:** ~25 ms - 40 ms (Target: < 200 ms)
   - **Host CPU:** Normal (e.g. 15% - 25%)
   - **Diagnostic Hero Card:** Green badge — `SYSTEM OPTIMAL: System Operating Normally (Within SLOs)`.
   - **Breakdown Bar:** Fast, balanced distribution between API, SQLite, and Payment.

### Step 3: Injecting the Main Scenario — Slow Database (90 seconds)
1. Click the **Injected Slow Database (+1.5s)** button.
2. Watch the dashboard update dynamically within 2-3 seconds:
   - **Total Request Latency:** Spikes from 35 ms to **~1,530 ms**.
   - **P95 Latency:** Red breach indicator — **1,550 ms** (Violating SLO Target: < 200 ms).
   - **Host CPU Usage:** Remains **completely normal** (e.g. 18% - 25%).
3. Highlight the **Intelligent Diagnostic Engine Card**:
   - **Likely Cause:** `Likely Cause: Database Response Latency`
   - **Affected Component:** `Database`
   - **CPU Ruling:**  
     *"CPU is normal (18.4%), ruling out CPU exhaustion as the root cause."*
   - **Empirical Evidence:**  
     Database accounts for **~1,480 ms (96.5%)** of total request time, while API processing (~12 ms) and Payment (~20 ms) are negligible.
   - **Actionable Engineering Remedies:**  
     - Inspect SQLite / PostgreSQL slow query logs and query plans (`EXPLAIN QUERY PLAN`).  
     - Check index coverage on `orders` and `inventory`.  
     - Investigate database locks and connection pool starvation.
4. **Key Takeaway to state:**  
   *"A traditional CPU dashboard would show green and alert nothing. SLI-X detects the SLO breach, proves that CPU is NOT responsible, identifies the Database as the true culprit, and suggests actionable fixes."*

### Step 4: Injecting Slow Payment Gateway (45 seconds)
1. Click **Injected Slow Payment (+1.5s)**.
2. Observe the instant transition:
   - Request latency remains elevated at ~1,530 ms.
   - The **Breakdown Bar** shifts from Database (amber) to Payment (purple).
   - **Diagnostic Hero Card:** Automatically updates to `Likely Cause: Payment Processing Delay`.
   - **Affected Component:** `Payment Gateway`.
   - **Recommended Fix:** Check third-party gateway latency, implement circuit breakers, and switch to asynchronous webhooks.

### Step 5: Restoration to Normal (30 seconds)
1. Click **Reset to Normal**.
2. Within 2 requests, latencies drop back down to ~30 ms.
3. P95 recovers to compliant green status.
4. Diagnosis automatically clears to `SYSTEM OPTIMAL`.
5. Open `http://127.0.0.1:8001/metrics` in a new tab to show the live Prometheus export format.

---

## 🧪 Automated Testing Verification

Run the test suite with:
```powershell
pytest -v tests/test_diagnostics.py
```

The automated test suite verifies:
1. **Rule 1 (Slow Database):** High latency, low CPU, DB dominant $\rightarrow$ Correctly diagnoses DB latency and rules out CPU.
2. **Rule 2 (Slow Payment):** High latency, low CPU, Payment dominant $\rightarrow$ Diagnoses Payment Gateway delay.
3. **Rule 3 (CPU Saturation):** High latency, CPU > 75%, API dominant $\rightarrow$ Diagnoses CPU Saturation.
4. **Rule 4 (High Error Rate):** Error rate > 1% $\rightarrow$ Diagnoses high error rate and identifies failing stage.
5. **Rule 5 (Inconclusive / Insufficient Data):** Inconclusive split or empty telemetry $\rightarrow$ Diagnoses "Unable to confidently identify bottleneck. More telemetry is required."
6. **Fault Injection Endpoints:** Full integration test confirming real runtime delays in `slow_database` and recovery upon reset.

---

## 📂 Project Structure

```
SLI-X/
├── app.py                  # FastAPI server, request instrumentation, demo endpoints
├── diagnostic_engine.py    # Core intelligent diagnostic engine implementing expert rules
├── metrics.py              # Rolling window SLI calculations & psutil host measurements
├── database.py             # SQLite order/inventory transactions & telemetry logging
├── templates/
│   └── index.html          # Professional dark-theme dashboard
├── static/
│   ├── style.css           # Modern CSS with animations, glowing pills, and responsive layout
│   └── dashboard.js        # Real-time polling, fault injection control, and metric updates
├── tests/
│   └── test_diagnostics.py # Automated test suite for rules and endpoints
├── requirements.txt        # Python dependency manifest
└── README.md               # Architecture documentation and presentation guide
```

---

## 🏆 Summary

SLI-X demonstrates that **Service Level Indicators (SLIs) and infrastructure metrics serve fundamentally different roles**. By instrumenting request breakdown times, SLI-X prevents engineering teams from misdiagnosing database and network wait states as compute bottlenecks, speeding up mean time to resolution (MTTR).

