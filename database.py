"""
database.py - SQLite storage for SLI-X requests and metrics history
"""
import sqlite3
import os
import time
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "slix.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency without blocking reads/writes
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    """Initializes SQLite schema for requests and e-commerce inventory."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table for telemetry recordings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS request_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT NOT NULL,
        timestamp REAL NOT NULL,
        total_latency_ms REAL NOT NULL,
        api_time_ms REAL NOT NULL,
        db_time_ms REAL NOT NULL,
        payment_time_ms REAL NOT NULL,
        success INTEGER NOT NULL,
        error_message TEXT,
        demo_mode TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON request_telemetry(timestamp)
    """)

    # Mock e-commerce orders & products table for actual DB operations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        sku TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        amount REAL NOT NULL,
        created_at REAL NOT NULL,
        status TEXT NOT NULL
    )
    """)

    # Seed sample products if not already present
    cursor.execute("SELECT COUNT(*) FROM inventory")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
        INSERT INTO inventory (sku, name, price, stock) VALUES (?, ?, ?, ?)
        """, [
            ("SKU-PRO-LAPTOP", "QuantumBook Pro 16", 1899.99, 50),
            ("SKU-MECH-KEYBOARD", "Vortex RGB Mechanical Keyboard", 149.50, 120),
            ("SKU-ANC-HEADSET", "AcousticZen Noise-Canceling Headset", 279.00, 85),
            ("SKU-4K-MONITOR", "UltraVision 4K 144Hz Monitor", 649.99, 40)
        ])

    conn.commit()
    conn.close()


def record_request_telemetry(
    request_id: str,
    timestamp: float,
    total_latency_ms: float,
    api_time_ms: float,
    db_time_ms: float,
    payment_time_ms: float,
    success: bool,
    error_message: Optional[str] = None,
    demo_mode: str = "normal"
):
    """Inserts an instrumented request record into SQLite."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO request_telemetry (
            request_id, timestamp, total_latency_ms, api_time_ms, db_time_ms, 
            payment_time_ms, success, error_message, demo_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request_id,
            timestamp,
            round(total_latency_ms, 2),
            round(api_time_ms, 2),
            round(db_time_ms, 2),
            round(payment_time_ms, 2),
            1 if success else 0,
            error_message,
            demo_mode
        ))
        conn.commit()
    finally:
        conn.close()


def get_recent_telemetry(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves the most recent telemetry entries."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT request_id, timestamp, total_latency_ms, api_time_ms, db_time_ms,
               payment_time_ms, success, error_message, demo_mode
        FROM request_telemetry
        ORDER BY id DESC
        LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def execute_ecommerce_db_operation(order_id: str, sku: str, quantity: int, amount: float):
    """Performs real SQLite reads and writes for the checkout process."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Query product details
        cursor.execute("SELECT stock, price FROM inventory WHERE sku = ?", (sku,))
        item = cursor.fetchone()
        if not item:
            raise ValueError(f"SKU '{sku}' not found in inventory")

        # Insert new order
        cursor.execute("""
        INSERT INTO orders (order_id, sku, quantity, amount, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (order_id, sku, quantity, amount, time.time(), "CONFIRMED"))

        # Decrement stock
        cursor.execute("UPDATE inventory SET stock = stock - ? WHERE sku = ?", (quantity, sku))
        conn.commit()
    finally:
        conn.close()

