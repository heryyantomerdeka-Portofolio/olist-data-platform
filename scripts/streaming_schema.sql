
CREATE SCHEMA IF NOT EXISTS stream;

CREATE TABLE IF NOT EXISTS stream.order_events (
    event_id       TEXT PRIMARY KEY,
    order_id       TEXT NOT NULL,
    status         TEXT NOT NULL,
    event_ts       TIMESTAMP NOT NULL,
    produced_at    TIMESTAMPTZ NOT NULL,
    consumed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_event   JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_order_events_order_ts
    ON stream.order_events (order_id, event_ts);

CREATE TABLE IF NOT EXISTS stream.order_current (
    order_id       TEXT PRIMARY KEY,
    status         TEXT NOT NULL,
    status_rank    INTEGER NOT NULL,
    event_ts       TIMESTAMP NOT NULL,
    event_id       TEXT NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stream.dlq_messages (
    dlq_id          TEXT PRIMARY KEY,
    source_topic    TEXT NOT NULL,
    source_partition INTEGER NOT NULL,
    source_offset   BIGINT NOT NULL,
    raw_message     TEXT,
    error_reason    TEXT NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stream.consumer_metrics (
    metric_id           BIGSERIAL PRIMARY KEY,
    batch_started_at    TIMESTAMPTZ NOT NULL,
    batch_finished_at   TIMESTAMPTZ NOT NULL,
    messages_received   INTEGER NOT NULL DEFAULT 0,
    new_events          INTEGER NOT NULL DEFAULT 0,
    duplicates_ignored  INTEGER NOT NULL DEFAULT 0,
    out_of_order        INTEGER NOT NULL DEFAULT 0,
    dlq_count           INTEGER NOT NULL DEFAULT 0,
    freshness_p50_ms    DOUBLE PRECISION,
    freshness_p95_ms    DOUBLE PRECISION
);
