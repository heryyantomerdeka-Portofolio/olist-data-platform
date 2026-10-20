"""Produce deterministic Olist order status events to Kafka."""

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

from scripts.streaming_common import (
    KAFKA_BOOTSTRAP,
    ORDERS_TOPIC,
    FAULT_LOG,
    PRODUCER_REPORT,
    connect_db,
    json_bytes,
    stable_event_id,
    utc_now_iso,
)

# A higher rank means a later business state.
# Terminal states are deliberately assigned the highest rank.
STATUS_RANK = {
    "created": 10,
    "approved": 20,
    "invoiced": 30,
    "processing": 40,
    "shipped": 50,
    "delivered": 60,
    "canceled": 100,
    "unavailable": 100,
}


def ensure_topic():
    admin = KafkaAdminClient(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        request_timeout_ms=15000,
    )
    try:
        existing = admin.list_topics()
        if ORDERS_TOPIC not in existing:
            admin.create_topics(
                [
                    NewTopic(
                        name=ORDERS_TOPIC,
                        num_partitions=3,
                        replication_factor=1,
                    )
                ],
                validate_only=False,
            )
            print(f"Topic dibuat: {ORDERS_TOPIC}")
        else:
            print(f"Topic sudah tersedia: {ORDERS_TOPIC}")
    finally:
        admin.close()


def parse_timestamp(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return None


def build_events(row):
    """Build a deterministic event history for one source order."""
    order_id = row["order_id"]
    final_status = row["order_status"]

    purchase = parse_timestamp(row["order_purchase_timestamp"])
    approved = parse_timestamp(row["order_approved_at"])
    carrier = parse_timestamp(row["order_delivered_carrier_date"])
    delivered = parse_timestamp(row["order_delivered_customer_date"])

    if purchase is None:
        raise ValueError(f"Order {order_id} has no purchase timestamp")

    transitions = [("created", purchase)]

    if approved:
        transitions.append(("approved", approved))

    # The source has no dedicated invoiced/processing timestamps.
    # Include these states only for orders whose final status requires them,
    # using the purchase timestamp as a documented synthetic event time.
    if final_status in {"invoiced", "processing"}:
        if final_status == "invoiced":
            transitions.append(("invoiced", purchase))
        else:
            transitions.extend(
                [("invoiced", purchase), ("processing", purchase)]
            )

    if carrier:
        transitions.append(("shipped", carrier))

    if delivered:
        transitions.append(("delivered", delivered))

    if final_status in {"canceled", "unavailable"}:
        transitions.append((final_status, purchase))
    elif final_status not in STATUS_RANK:
        raise ValueError(f"Unknown order status: {final_status}")

    # Ensure the exact source status is represented even if its timestamp
    # was absent or the source's intermediate timestamps were incomplete.
    represented = {status for status, _ in transitions}
    if final_status not in represented:
        transitions.append((final_status, purchase))

    # Sort by event timestamp, then status rank. The consumer will use rank
    # to prevent late events from regressing the current state.
    transitions.sort(key=lambda item: (item[1], STATUS_RANK[item[0]]))

    events = []
    seen = set()
    for status, event_ts in transitions:
        event_ts_iso = event_ts.isoformat(sep=" ")
        event_id = stable_event_id(order_id, status, event_ts_iso)

        if event_id in seen:
            continue
        seen.add(event_id)

        events.append(
            {
                "event_id": event_id,
                "order_id": order_id,
                "status": status,
                "status_rank": STATUS_RANK[status],
                "event_ts": event_ts_iso,
                "produced_at": utc_now_iso(),
                "source_status": final_status,
            }
        )

    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="Test with the first N orders; 0 means all")
    parser.add_argument("--no-faults", action="store_true",
                        help="Disable duplicate, delayed and malformed injection")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    ensure_topic()

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        acks="all",
        retries=5,
        max_block_ms=30000,
        key_serializer=lambda key: key.encode("utf-8"),
        value_serializer=lambda value: value if isinstance(value, bytes)
        else json_bytes(value),
    )

    started = time.monotonic()
    base_events = []
    order_count = 0

    try:
        with connect_db() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT order_id, order_status,
                           order_purchase_timestamp, order_approved_at,
                           order_delivered_carrier_date,
                           order_delivered_customer_date
                    FROM raw.orders
                    ORDER BY order_purchase_timestamp, order_id
                """
                if args.limit > 0:
                    query += " LIMIT %s"
                    cur.execute(query, (args.limit,))
                else:
                    cur.execute(query)

                columns = [d.name for d in cur.description]
                for values in cur:
                    row = dict(zip(columns, values))
                    order_count += 1
                    base_events.extend(build_events(row))

        # Preserve event chronology before applying controlled faults.
        base_events.sort(key=lambda e: (e["event_ts"], e["order_id"]))

        fault_counts = {
            "base_events": len(base_events),
            "duplicate_injected": 0,
            "delayed_injected": 0,
            "malformed_injected": 0,
        }

        to_send = []
        for event in base_events:
            if not args.no_faults and rng.random() < 0.03:
                to_send.append((event, "duplicate"))
                fault_counts["duplicate_injected"] += 1

            if not args.no_faults and rng.random() < 0.02:
                to_send.append((event, "delayed"))
                fault_counts["delayed_injected"] += 1

            to_send.append((event, "normal"))

            if not args.no_faults and rng.random() < 0.005:
                malformed_type = rng.choice(
                    ["invalid_json", "missing_field", "bad_timestamp"]
                )
                if malformed_type == "invalid_json":
                    bad_value = b"{this-is-not-json"
                elif malformed_type == "missing_field":
                    bad_value = json_bytes(
                        {"order_id": event["order_id"],
                         "status": event["status"]}
                    )
                else:
                    bad_event = dict(event)
                    bad_event["event_ts"] = "not-a-timestamp"
                    bad_value = json_bytes(bad_event)

                to_send.append(
                    (
                        {
                            "order_id": event["order_id"],
                            "_raw_value": bad_value,
                            "_fault": malformed_type,
                        },
                        "malformed",
                    )
                )
                fault_counts["malformed_injected"] += 1

        # Delayed events are sent after the normal stream. Their event_ts
        # remains unchanged to simulate late arrival.
        normal_and_duplicate = [
            pair for pair in to_send if pair[1] != "delayed"
        ]
        delayed = [pair for pair in to_send if pair[1] == "delayed"]
        send_sequence = normal_and_duplicate + delayed

        send_futures = []

        for event, kind in send_sequence:
            if kind == "malformed":
                value = event["_raw_value"]
                key = event["order_id"]
            else:
                value = dict(event)
                if kind == "duplicate":
                    value["injected_duplicate"] = True
                key = event["order_id"]

            future = producer.send(
                ORDERS_TOPIC,
                key=key,
                value=value,
            )
            send_futures.append(future)

        # Pastikan pengiriman selesai dan laporkan kegagalan asynchronous.
        producer.flush(timeout=120)

        delivery_errors = []
        for index, future in enumerate(send_futures):
            try:
                future.get(timeout=5)
            except Exception as exc:
                delivery_errors.append({
                    "message_index": index,
                    "error": f"{type(exc).__name__}: {exc}",
                })

        if delivery_errors:
            raise RuntimeError(
                f"{len(delivery_errors)} pesan gagal dikirim ke Kafka. "
                f"Contoh: {delivery_errors[:3]}"
            )


        elapsed = time.monotonic() - started
        report = {
            "generated_at": utc_now_iso(),
            "source_orders": order_count,
            "unique_base_events": len(base_events),
            "faults": fault_counts,
            "topic": ORDERS_TOPIC,
            "elapsed_seconds": round(elapsed, 3),
            "seed": args.seed,
            "faults_enabled": not args.no_faults,
        }

        FAULT_LOG.write_text(
            json.dumps(fault_counts, indent=2),
            encoding="utf-8",
        )
        PRODUCER_REPORT.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        print(json.dumps(report, indent=2))

    finally:
        producer.close(timeout=30)


if __name__ == "__main__":
    main()
