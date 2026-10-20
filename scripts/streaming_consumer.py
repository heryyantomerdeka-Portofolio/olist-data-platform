
"""Kafka consumer with PostgreSQL idempotency, validation and DLQ."""

import argparse
import json
import time
import hashlib
import os
from datetime import datetime, timezone

from kafka import KafkaConsumer, KafkaProducer
from kafka.structs import OffsetAndMetadata, TopicPartition
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

from scripts.streaming_common import (
    KAFKA_BOOTSTRAP,
    ORDERS_TOPIC,
    DLQ_TOPIC,
    CONSUMER_GROUP,
    connect_db,
    json_bytes,
    utc_now_iso,
)


REQUIRED_FIELDS = {
    "event_id",
    "order_id",
    "status",
    "status_rank",
    "event_ts",
    "produced_at",
}


def ensure_dlq_topic():
    admin = KafkaAdminClient(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        request_timeout_ms=15000,
    )
    try:
        if DLQ_TOPIC not in admin.list_topics():
            admin.create_topics(
                [NewTopic(DLQ_TOPIC, num_partitions=3, replication_factor=1)]
            )
            print(f"Topic DLQ dibuat: {DLQ_TOPIC}")
        else:
            print(f"Topic DLQ sudah tersedia: {DLQ_TOPIC}")
    finally:
        admin.close()


def parse_iso(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp harus berupa string non-kosong")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    # event_ts from PostgreSQL source is naive local timestamp.
    # Preserve its naive representation for the TIMESTAMP column.
    if result.tzinfo is not None:
        result = result.astimezone(timezone.utc).replace(tzinfo=None)
    return result


def validate_event(payload):
    if not isinstance(payload, dict):
        raise ValueError("JSON event harus berupa object")

    missing = REQUIRED_FIELDS - set(payload)
    if missing:
        raise ValueError(f"field wajib tidak ada: {sorted(missing)}")

    for name in ("event_id", "order_id", "status"):
        if not isinstance(payload[name], str) or not payload[name].strip():
            raise ValueError(f"{name} harus berupa string non-kosong")

    if isinstance(payload["status_rank"], bool) or not isinstance(
        payload["status_rank"], int
    ):
        raise ValueError("status_rank harus berupa integer")

    event_ts = parse_iso(payload["event_ts"])
    produced_at = datetime.fromisoformat(
        payload["produced_at"].replace("Z", "+00:00")
    )
    if produced_at.tzinfo is None:
        produced_at = produced_at.replace(tzinfo=timezone.utc)

    return event_ts, produced_at


def write_dlq(db, dlq_producer, message, raw_text, reason):
    dlq_id = hashlib.sha256(
        f"{message.topic}|{message.partition}|{message.offset}".encode()
    ).hexdigest()

    dlq_record = {
        "dlq_id": dlq_id,
        "source_topic": message.topic,
        "source_partition": message.partition,
        "source_offset": message.offset,
        "raw_message": raw_text,
        "error_reason": reason,
        "received_at": utc_now_iso(),
    }

    # The database record is idempotent by source topic/partition/offset.
    # Publish to the DLQ topic before committing the source offset.
    # Kafka and PostgreSQL do not share a distributed transaction, so the
    # topic can receive a duplicate if the process crashes before offset commit.
    dlq_producer.send(
        DLQ_TOPIC,
        key=dlq_id.encode("utf-8"),
        value=json_bytes(dlq_record),
    ).get(timeout=15)

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stream.dlq_messages (
                dlq_id, source_topic, source_partition, source_offset,
                raw_message, error_reason
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (dlq_id) DO NOTHING
            """,
            (
                dlq_id,
                message.topic,
                message.partition,
                message.offset,
                raw_text,
                reason,
            ),
        )


def process_valid_event(db, payload, event_ts, produced_at, consumed_at):
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stream.order_events (
                event_id, order_id, status, event_ts,
                produced_at, consumed_at, source_event
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (event_id) DO NOTHING
            RETURNING event_id
            """,
            (
                payload["event_id"],
                payload["order_id"],
                payload["status"],
                event_ts,
                produced_at,
                consumed_at,
                json.dumps(payload),
            ),
        )
        inserted = cur.fetchone() is not None

        if not inserted:
            return {"new": 0, "duplicate": 1, "out_of_order": 0, "freshness_ms": None}

        cur.execute(
            """
            SELECT status_rank, event_ts
            FROM stream.order_current
            WHERE order_id = %s
            """,
            (payload["order_id"],),
        )
        current = cur.fetchone()
        out_of_order = int(
            current is not None
            and (
                event_ts < current[1]
                or payload["status_rank"] < current[0]
            )
        )

        # Monotonic rank prevents late lower-rank events from regressing
        # current status. For equal ranks, only a newer timestamp can win.
        cur.execute(
            """
            INSERT INTO stream.order_current (
                order_id, status, status_rank, event_ts, event_id, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (order_id) DO UPDATE
            SET status = EXCLUDED.status,
                status_rank = EXCLUDED.status_rank,
                event_ts = EXCLUDED.event_ts,
                event_id = EXCLUDED.event_id,
                updated_at = NOW()
            WHERE
                EXCLUDED.status_rank > stream.order_current.status_rank
                OR (
                    EXCLUDED.status_rank = stream.order_current.status_rank
                    AND EXCLUDED.event_ts > stream.order_current.event_ts
                )
            """,
            (
                payload["order_id"],
                payload["status"],
                payload["status_rank"],
                event_ts,
                payload["event_id"],
            ),
        )

    freshness_ms = (
        consumed_at - produced_at
    ).total_seconds() * 1000.0

    return {
        "new": 1,
        "duplicate": 0,
        "out_of_order": out_of_order,
        "freshness_ms": freshness_ms,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-messages", type=int, default=0,
                        help="Stop after N consumed messages; 0 means idle timeout")
    parser.add_argument("--idle-timeout", type=int, default=10,
                        help="Stop after this many seconds without new messages")
    parser.add_argument("--group-id", default=CONSUMER_GROUP)
    args = parser.parse_args()

    ensure_dlq_topic()

    consumer = KafkaConsumer(
        ORDERS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=args.group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        key_deserializer=None,
        value_deserializer=None,
        consumer_timeout_ms=1000,
        max_poll_records=500,
    )

    dlq_producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        acks="all",
        retries=5,
    )

    stats = {
        "messages_received": 0,
        "new_events": 0,
        "duplicates_ignored": 0,
        "out_of_order": 0,
        "dlq_count": 0,
        "freshness_ms": [],
    }
    started_at = datetime.now(timezone.utc)
    last_message_at = time.monotonic()

    try:
        while True:
            records = consumer.poll(timeout_ms=1000, max_records=500)
            got_message = False

            for _tp, messages in records.items():
                for message in messages:
                    got_message = True
                    last_message_at = time.monotonic()
                    stats["messages_received"] += 1
                    consumed_at = datetime.now(timezone.utc)
                    raw_text = message.value.decode("utf-8", errors="replace") if message.value else ""

                    try:
                        payload = json.loads(message.value.decode("utf-8"))
                        event_ts, produced_at = validate_event(payload)

                        with connect_db() as db:
                            result = process_valid_event(
                                db, payload, event_ts, produced_at, consumed_at
                            )

                        stats["new_events"] += result["new"]
                        stats["duplicates_ignored"] += result["duplicate"]
                        stats["out_of_order"] += result["out_of_order"]
                        if result["freshness_ms"] is not None:
                            stats["freshness_ms"].append(result["freshness_ms"])

                    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                        with connect_db() as db:
                            write_dlq(
                                db, dlq_producer, message, raw_text,
                                f"{type(exc).__name__}: {exc}",
                            )
                        stats["dlq_count"] += 1

                    # T6 failure injection:
                    # crash after DB processing but before Kafka offset commit.
                    if (
                        os.getenv("FAIL_BEFORE_OFFSET_COMMIT", "").lower()
                        in {"1", "true", "yes"}
                    ):
                        print(
                            "T6_INJECTED_CRASH_BEFORE_OFFSET_COMMIT "
                            f"topic={message.topic} "
                            f"partition={message.partition} "
                            f"offset={message.offset}",
                            flush=True,
                        )
                        os._exit(86)

                    # Commit only the message successfully processed.
                    # Kafka offsets store the NEXT offset to consume.
                    partition = TopicPartition(message.topic, message.partition)
                    next_offset = message.offset + 1

                    consumer.commit({
                        partition: OffsetAndMetadata(next_offset, "")
                    })

                    if args.max_messages and stats["messages_received"] >= args.max_messages:
                        break

                if args.max_messages and stats["messages_received"] >= args.max_messages:
                    break

            if args.max_messages and stats["messages_received"] >= args.max_messages:
                break

            if not got_message and time.monotonic() - last_message_at >= args.idle_timeout:
                break

        import statistics

        values = sorted(stats["freshness_ms"])
        def percentile(p):
            if not values:
                return None
            index = round((len(values) - 1) * p)
            return round(values[index], 3)

        finished_at = datetime.now(timezone.utc)
        with connect_db() as db:
            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO stream.consumer_metrics (
                        batch_started_at, batch_finished_at, messages_received,
                        new_events, duplicates_ignored, out_of_order,
                        dlq_count, freshness_p50_ms, freshness_p95_ms
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        started_at, finished_at, stats["messages_received"],
                        stats["new_events"], stats["duplicates_ignored"],
                        stats["out_of_order"], stats["dlq_count"],
                        percentile(0.50), percentile(0.95),
                    ),
                )

        print(json.dumps({
            **stats,
            "freshness_p50_ms": percentile(0.50),
            "freshness_p95_ms": percentile(0.95),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        }, indent=2, default=str))

    finally:
        consumer.close()
        dlq_producer.close(timeout=30)


if __name__ == "__main__":
    main()

