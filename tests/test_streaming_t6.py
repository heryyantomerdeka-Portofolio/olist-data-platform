
import pytest

from scripts.streaming_common import stable_event_id
from scripts.streaming_producer import build_events
from scripts.streaming_consumer import validate_event


def test_event_id_is_deterministic():
    first = stable_event_id(
        "order-test-001", "created", "2018-01-01 10:00:00"
    )
    second = stable_event_id(
        "order-test-001", "created", "2018-01-01 10:00:00"
    )

    assert first == second


def test_event_id_changes_when_status_changes():
    created = stable_event_id(
        "order-test-001", "created", "2018-01-01 10:00:00"
    )
    delivered = stable_event_id(
        "order-test-001", "delivered", "2018-01-01 10:00:00"
    )

    assert created != delivered


def test_producer_rejects_missing_required_source_column():
    # order_status sengaja tidak tersedia.
    row = {
        "order_id": "order-test-001",
        "order_purchase_timestamp": "2018-01-01 10:00:00",
        "order_approved_at": None,
        "order_delivered_carrier_date": None,
        "order_delivered_customer_date": None,
    }

    with pytest.raises(KeyError, match="order_status"):
        build_events(row)


def test_producer_rejects_missing_purchase_timestamp():
    row = {
        "order_id": "order-test-001",
        "order_status": "created",
        "order_purchase_timestamp": None,
        "order_approved_at": None,
        "order_delivered_carrier_date": None,
        "order_delivered_customer_date": None,
    }

    with pytest.raises(ValueError, match="purchase timestamp"):
        build_events(row)


def test_consumer_rejects_event_missing_required_field():
    payload = {
        "event_id": "event-test-001",
        "order_id": "order-test-001",
        "status": "created",
        "status_rank": 10,
        "event_ts": "2018-01-01 10:00:00",
        # produced_at sengaja dihilangkan.
    }

    with pytest.raises(ValueError, match="field wajib tidak ada"):
        validate_event(payload)


def test_consumer_rejects_invalid_timestamp():
    payload = {
        "event_id": "event-test-001",
        "order_id": "order-test-001",
        "status": "created",
        "status_rank": 10,
        "event_ts": "not-a-timestamp",
        "produced_at": "2018-01-01T10:00:00+00:00",
    }

    with pytest.raises(ValueError):
        validate_event(payload)
