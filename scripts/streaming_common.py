
"""Shared configuration and helpers for Olist Kafka streaming."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
ORDERS_TOPIC = os.getenv("KAFKA_ORDERS_TOPIC", "olist.order-events")
DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "olist.order-events.dlq")
CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "olist-stream-consumer")

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
DB_NAME = os.getenv("POSTGRES_DB", "olist")
DB_USER = os.getenv("POSTGRES_USER", "olist")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FAULT_LOG = OUTPUT_DIR / "stream_fault_injection.json"
PRODUCER_REPORT = OUTPUT_DIR / "producer_report.json"


def connect_db():
    """Connect to the project PostgreSQL database."""
    import psycopg

    if not DB_PASSWORD:
        raise RuntimeError(
            "POSTGRES_PASSWORD belum disetel. "
            "Pastikan tersedia di environment atau file .env."
        )

    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=10,
    )


def stable_event_id(order_id: str, status: str, event_ts: str) -> str:
    """Create a deterministic ID so replayed events are idempotent."""
    raw = f"{order_id}|{status}|{event_ts}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
