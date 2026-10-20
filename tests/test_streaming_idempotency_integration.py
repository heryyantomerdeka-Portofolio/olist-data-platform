
"""Integration test: database idempotency for stream events."""

from datetime import datetime, timezone

from scripts.streaming_common import connect_db
from scripts.streaming_consumer import process_valid_event


def test_replayed_event_is_not_inserted_twice():
    order_id = "t6-test-idempotency-001"
    event_id = "t6-test-event-001"
    event_ts = datetime(2018, 1, 1, 10, 0, 0)
    produced_at = datetime.now(timezone.utc)
    payload = {
        "event_id": event_id,
        "order_id": order_id,
        "status": "created",
        "status_rank": 10,
        "event_ts": event_ts.isoformat(sep=" "),
        "produced_at": produced_at.isoformat(),
    }

    try:
        with connect_db() as db:
            first = process_valid_event(
                db, payload, event_ts, produced_at,
                datetime.now(timezone.utc),
            )

        with connect_db() as db:
            second = process_valid_event(
                db, payload, event_ts, produced_at,
                datetime.now(timezone.utc),
            )

        assert first["new"] == 1
        assert second["new"] == 0
        assert second["duplicate"] == 1

        with connect_db() as db:
            with db.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM stream.order_events
                    WHERE event_id = %s
                    """,
                    (event_id,),
                )
                assert cur.fetchone()[0] == 1

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM stream.order_current
                    WHERE order_id = %s
                    """,
                    (order_id,),
                )
                assert cur.fetchone()[0] == 1

    finally:
        # Hanya menghapus record khusus tes ini.
        with connect_db() as db:
            with db.cursor() as cur:
                cur.execute(
                    "DELETE FROM stream.order_current WHERE order_id = %s",
                    (order_id,),
                )
                cur.execute(
                    "DELETE FROM stream.order_events WHERE event_id = %s",
                    (event_id,),
                )
