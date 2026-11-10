"""
demo_cli.py - Interactive Terminal Demonstration for SLI-X.

Runs an automated, terminal-based live demonstration showcasing:
1. Normal Baseline Traffic (Low Latency, Normal CPU)
2. Injected Slow Database (Spike in Latency, Normal CPU, Root Cause: Database)
3. Injected Slow Payment (Spike in Latency, Normal CPU, Root Cause: Payment)
4. Recovery to Normal

Perfect for live viva presentations or command-line demonstrations.
"""
import sys
import os
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import (
    process_ecommerce_request,
    set_current_demo_mode,
    get_current_demo_mode
)
from metrics import metrics_collector
from diagnostic_engine import diagnostic_engine

# ANSI Color Codes for terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    print(f"\n{CYAN}{BOLD}{'='*70}{RESET}")
    print(f"{CYAN}{BOLD}   ⚡ SLI-X — Smart Reliability Intelligence: CLI Demonstration{RESET}")
    print(f"{CYAN}{BOLD}{'='*70}{RESET}\n")


def print_step_header(step_num: int, title: str):
    print(f"\n{BOLD}{YELLOW}[STEP {step_num}] {title}{RESET}")
    print(f"{'-'*70}")


def run_requests_and_diagnose(count: int = 4, delay: float = 0.5):
    """Executes a batch of requests and prints real-time diagnosis."""
    for i in range(1, count + 1):
        res = process_ecommerce_request()
        lat = res["latency_ms"]
        print(
            f"  Request {i}/{count} | ID: {res['request_id']} | "
            f"Total: {BOLD}{lat['total']:.1f}ms{RESET} (API: {lat['api_processing']:.1f}ms, "
            f"DB: {lat['database_operation']:.1f}ms, Pay: {lat['payment_operation']:.1f}ms)"
        )
        time.sleep(delay)

    # Evaluate current SLIs and diagnosis
    slis = metrics_collector.calculate_slis()
    infra = metrics_collector.get_infrastructure_metrics()
    diag = diagnostic_engine.diagnose(slis=slis, infrastructure=infra)

    # Colorize status
    status = diag["status"]
    status_color = GREEN if status == "HEALTHY" else (RED if status == "CRITICAL" else YELLOW)

    print(f"\n  {BOLD}Diagnostic Telemetry Summary:{RESET}")
    print(f"  • P95 Latency   : {BOLD}{slis['p95_latency_ms']:.1f} ms{RESET} (SLO Target: < 200 ms)")
    print(f"  • Availability  : {BOLD}{slis['availability_pct']:.1f} %{RESET} (SLO Target: >= 99.9%)")
    print(f"  • Host CPU      : {BOLD}{infra['cpu_usage_pct']:.1f} %{RESET} (Threshold: < 75%)")
    print(f"  • Host Memory   : {BOLD}{infra['memory_usage_pct']:.1f} %{RESET}")
    print(f"  • Status        : {status_color}{BOLD}{status}{RESET}")
    print(f"  • Likely Cause  : {status_color}{BOLD}{diag['likely_cause']}{RESET}")
    print(f"  • Component     : {BOLD}{diag['affected_component']}{RESET}")
    print(f"  • CPU Ruling    : {CYAN}{diag['cpu_assessment']}{RESET}")
    print(f"\n  {BOLD}Recommended Remediation:{RESET}")
    for fix in diag["recommended_fix"][:2]:
        print(f"    ✔ {fix}")
    print(f"{'-'*70}")


def main():
    print_banner()

    # STEP 1: NORMAL BASELINE
    print_step_header(1, "NORMAL BASELINE OPERATION")
    print("Configuring system for Normal Mode (no injected delays)...")
    set_current_demo_mode("normal")
    run_requests_and_diagnose(count=3, delay=0.3)

    # STEP 2: SLOW DATABASE FAULT INJECTION
    print_step_header(2, "FAULT INJECTION: SLOW DATABASE (+1.5s delay)")
    print(f"{YELLOW}Simulating unindexed query / transaction lock inside SQLite...{RESET}")
    set_current_demo_mode("slow_database")
    run_requests_and_diagnose(count=2, delay=0.2)

    # STEP 3: SLOW PAYMENT FAULT INJECTION
    print_step_header(3, "FAULT INJECTION: SLOW PAYMENT GATEWAY (+1.5s delay)")
    print(f"{MAGENTA}Simulating external payment gateway timeout/latency...{RESET}")
    set_current_demo_mode("slow_payment")
    run_requests_and_diagnose(count=2, delay=0.2)

    # STEP 4: RECOVERY TO NORMAL
    print_step_header(4, "SYSTEM RECOVERY: RESET TO NORMAL MODE")
    print("Clearing fault injection and restoring standard operation...")
    set_current_demo_mode("normal")
    run_requests_and_diagnose(count=3, delay=0.2)

    print(f"\n{GREEN}{BOLD}✔ Live CLI Demonstration completed successfully!{RESET}\n")


if __name__ == "__main__":
    main()
