
CREATE SCHEMA IF NOT EXISTS mart;

-- Rebuild only T5 marts; does not modify raw, silver, or dw.
DROP TABLE IF EXISTS mart.monthly_sales;
DROP TABLE IF EXISTS mart.delivery_performance;
DROP TABLE IF EXISTS mart.seller_scorecard;
DROP TABLE IF EXISTS mart.customer_rfm;
DROP TABLE IF EXISTS mart.stream_freshness;
DROP TABLE IF EXISTS mart.order_reconciliation;

-- 1. Monthly sales: delivered orders, merchandise revenue excludes freight.
CREATE TABLE mart.monthly_sales AS
SELECT
    d.month_start,
    COALESCE(p.product_category_english, 'unknown') AS category,
    COALESCE(g.state, 'unknown') AS customer_state,
    COUNT(DISTINCT o.order_id) AS delivered_orders,
    COUNT(*) AS item_lines,
    ROUND(SUM(i.price)::numeric, 2) AS merchandise_revenue,
    ROUND(SUM(i.freight_value)::numeric, 2) AS freight_revenue,
    ROUND(SUM(i.price + i.freight_value)::numeric, 2) AS merchandise_plus_freight
FROM dw.fact_order o
JOIN dw.fact_order_item i ON i.order_id = o.order_id
LEFT JOIN dw.dim_date d ON d.date_key = o.purchase_date_key
LEFT JOIN dw.dim_product p ON p.product_id = i.product_id
LEFT JOIN dw.dim_geo g
    ON g.zip_code_prefix = o.customer_zip_code_prefix
WHERE o.order_status = 'delivered'
GROUP BY
    d.month_start,
    COALESCE(p.product_category_english, 'unknown'),
    COALESCE(g.state, 'unknown');

CREATE INDEX ON mart.monthly_sales (month_start);
CREATE INDEX ON mart.monthly_sales (category, customer_state);


-- 2. Delivery performance: late-rate denominator is known is_late only.
CREATE TABLE mart.delivery_performance AS
SELECT
    d.month_start,
    COALESCE(g.state, 'unknown') AS customer_state,
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (
        WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
    ) AS delivered_orders,
    COUNT(*) FILTER (WHERE o.is_late IS TRUE) AS late_orders,
    COUNT(*) FILTER (WHERE o.is_late IS FALSE) AS on_time_orders,
    COUNT(*) FILTER (WHERE o.is_late IS NOT NULL) AS known_delivery_orders,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE o.is_late IS TRUE)
        / NULLIF(COUNT(*) FILTER (WHERE o.is_late IS NOT NULL), 0),
        2
    ) AS late_rate_pct,
    ROUND(
        AVG(
            EXTRACT(EPOCH FROM (
                o.order_delivered_customer_date - o.order_purchase_timestamp
            )) / 86400.0
        ) FILTER (
            WHERE o.order_status = 'delivered'
              AND o.order_delivered_customer_date IS NOT NULL
        )::numeric,
        2
    ) AS avg_delivery_days,
    ROUND(AVG(r.review_score)::numeric, 2) AS avg_review_score
FROM dw.fact_order o
LEFT JOIN dw.dim_date d ON d.date_key = o.purchase_date_key
LEFT JOIN dw.dim_geo g
    ON g.zip_code_prefix = o.customer_zip_code_prefix
LEFT JOIN dw.fact_review r ON r.order_id = o.order_id
GROUP BY d.month_start, COALESCE(g.state, 'unknown');

CREATE INDEX ON mart.delivery_performance (month_start, customer_state);


-- 3. Seller scorecard. Ratios are based on distinct orders, not item lines.
CREATE TABLE mart.seller_scorecard AS
WITH seller_order AS (
    SELECT
        i.seller_id,
        i.order_id,
        BOOL_OR(o.order_status = 'delivered') AS is_delivered,
        BOOL_OR(o.is_late IS TRUE) AS is_late,
        AVG(r.review_score)::numeric AS review_score
    FROM dw.fact_order_item i
    JOIN dw.fact_order o ON o.order_id = i.order_id
    LEFT JOIN dw.fact_review r ON r.order_id = o.order_id
    GROUP BY i.seller_id, i.order_id
),
seller_item AS (
    SELECT
        seller_id,
        COUNT(*) AS item_lines,
        ROUND(SUM(price)::numeric, 2) AS merchandise_revenue,
        ROUND(SUM(freight_value)::numeric, 2) AS freight_value
    FROM dw.fact_order_item
    GROUP BY seller_id
),
seller_orders AS (
    SELECT
        seller_id,
        COUNT(*) AS total_orders,
        COUNT(*) FILTER (WHERE is_delivered) AS delivered_orders,
        COUNT(*) FILTER (WHERE is_late) AS late_orders,
        ROUND(AVG(review_score), 2) AS avg_review_score
    FROM seller_order
    GROUP BY seller_id
)
SELECT
    s.seller_id,
    s.state AS seller_state,
    so.total_orders,
    so.delivered_orders,
    so.late_orders,
    ROUND(
        100.0 * so.late_orders / NULLIF(so.total_orders, 0), 2
    ) AS late_order_rate_pct,
    so.avg_review_score,
    si.item_lines,
    si.merchandise_revenue,
    si.freight_value,
    (so.total_orders >= 10) AS is_eligible_for_comparison
FROM dw.dim_seller s
LEFT JOIN seller_orders so ON so.seller_id = s.seller_id
LEFT JOIN seller_item si ON si.seller_id = s.seller_id;

CREATE INDEX ON mart.seller_scorecard (is_eligible_for_comparison);


-- 4. Customer RFM. Frequency score is rule-based, not a raw quintile.
-- Reference date is the latest purchase timestamp in the dataset.
CREATE TABLE mart.customer_rfm AS
WITH item_by_order AS (
    SELECT
        order_id,
        SUM(price)::numeric AS merchandise_spend
    FROM dw.fact_order_item
    GROUP BY order_id
),
customer_orders AS (
    SELECT
        o.customer_unique_id,
        o.order_id,
        o.order_purchase_timestamp,
        COALESCE(i.merchandise_spend, 0) AS merchandise_spend
    FROM dw.fact_order o
    LEFT JOIN item_by_order i ON i.order_id = o.order_id
    WHERE o.customer_unique_id IS NOT NULL
      AND o.order_status = 'delivered'
),
reference_date AS (
    SELECT MAX(order_purchase_timestamp)::date AS max_purchase_date
    FROM dw.fact_order
),
rfm_base AS (
    SELECT
        customer_unique_id,
        COUNT(DISTINCT order_id) AS frequency,
        MAX(order_purchase_timestamp)::date AS last_purchase_date,
        SUM(merchandise_spend) AS monetary_value
    FROM customer_orders
    GROUP BY customer_unique_id
),
rfm_scored AS (
    SELECT
        b.*,
        r.max_purchase_date AS reference_date,
        (r.max_purchase_date - b.last_purchase_date) AS recency_days,
        CASE
            WHEN b.frequency = 1 THEN 1
            WHEN b.frequency = 2 THEN 2
            WHEN b.frequency BETWEEN 3 AND 4 THEN 3
            WHEN b.frequency BETWEEN 5 AND 7 THEN 4
            WHEN b.frequency >= 8 THEN 5
            ELSE 1
        END AS frequency_score,
        NTILE(5) OVER (ORDER BY b.monetary_value) AS monetary_score
    FROM rfm_base b
    CROSS JOIN reference_date r
)
SELECT
    customer_unique_id,
    reference_date,
    last_purchase_date,
    recency_days,
    frequency,
    ROUND(monetary_value, 2) AS monetary_value,
    CASE
        WHEN recency_days <= 30 THEN 5
        WHEN recency_days <= 90 THEN 4
        WHEN recency_days <= 180 THEN 3
        WHEN recency_days <= 365 THEN 2
        ELSE 1
    END AS recency_score,
    frequency_score,
    monetary_score,
    CONCAT(
        CASE
            WHEN recency_days <= 30 THEN 5
            WHEN recency_days <= 90 THEN 4
            WHEN recency_days <= 180 THEN 3
            WHEN recency_days <= 365 THEN 2
            ELSE 1
        END,
        frequency_score,
        monetary_score
    ) AS rfm_segment_code
FROM rfm_scored;

CREATE INDEX ON mart.customer_rfm (frequency_score, recency_score);


-- 5. Stream freshness: one record per minute of batch completion.
CREATE TABLE mart.stream_freshness AS
SELECT
    date_trunc('minute', batch_finished_at) AS batch_minute,
    COUNT(*) AS batches,
    SUM(messages_received) AS messages_received,
    SUM(new_events) AS new_events,
    SUM(duplicates_ignored) AS duplicates_ignored,
    SUM(out_of_order) AS out_of_order,
    SUM(dlq_count) AS dlq_count,
    ROUND(AVG(freshness_p50_ms)::numeric, 2) AS avg_freshness_p50_ms,
    ROUND(AVG(freshness_p95_ms)::numeric, 2) AS avg_freshness_p95_ms,
    MAX(freshness_p95_ms) AS max_freshness_p95_ms,
    MIN(batch_started_at) AS first_batch_started_at,
    MAX(batch_finished_at) AS last_batch_finished_at
FROM stream.consumer_metrics
WHERE batch_finished_at IS NOT NULL
GROUP BY date_trunc('minute', batch_finished_at);

CREATE INDEX ON mart.stream_freshness (batch_minute);


-- 6. Order reconciliation: compare items + freight to total payment.
-- voucher/installment classes are diagnostic indicators, not proven causes.
CREATE TABLE mart.order_reconciliation AS
WITH item_totals AS (
    SELECT
        order_id,
        SUM(price)::numeric AS item_value,
        SUM(price + freight_value)::numeric AS item_plus_freight
    FROM dw.fact_order_item
    GROUP BY order_id
),
payment_totals AS (
    SELECT
        order_id,
        SUM(payment_value)::numeric AS paid_value,
        BOOL_OR(payment_type = 'voucher') AS has_voucher,
        BOOL_OR(payment_installments > 1) AS has_installments
    FROM dw.fact_payment
    GROUP BY order_id
),
recon AS (
    SELECT
        o.order_id,
        o.order_status,
        COALESCE(i.item_value, 0) AS item_value,
        COALESCE(i.item_plus_freight, 0) AS item_plus_freight,
        p.paid_value,
        COALESCE(p.has_voucher, FALSE) AS has_voucher,
        COALESCE(p.has_installments, FALSE) AS has_installments,
        CASE
            WHEN i.order_id IS NULL THEN 'without_items'
            WHEN p.order_id IS NULL THEN 'without_payment'
            WHEN ABS(i.item_plus_freight - p.paid_value) <= 0.01
                THEN 'matched'
            WHEN p.has_voucher THEN 'voucher_related'
            WHEN p.has_installments THEN 'installment_related'
            ELSE 'unexplained'
        END AS reconciliation_class
    FROM dw.fact_order o
    LEFT JOIN item_totals i ON i.order_id = o.order_id
    LEFT JOIN payment_totals p ON p.order_id = o.order_id
)
SELECT
    order_id,
    order_status,
    ROUND(item_value, 2) AS item_value,
    ROUND(item_plus_freight, 2) AS item_plus_freight,
    ROUND(paid_value, 2) AS paid_value,
    ROUND(paid_value - item_plus_freight, 2) AS difference_paid_minus_items_freight,
    has_voucher,
    has_installments,
    reconciliation_class,
    CASE
        WHEN reconciliation_class = 'unexplained'
            THEN ABS(paid_value - item_plus_freight)
        ELSE 0::numeric
    END AS unexplained_abs_difference
FROM recon;

CREATE INDEX ON mart.order_reconciliation (reconciliation_class);
