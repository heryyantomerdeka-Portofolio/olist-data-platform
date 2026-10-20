
-- ============================================================
-- Olist Data Platform - T4 Star Schema
-- PostgreSQL
--
-- Rebuilds ONLY schema dw. Does not modify raw or stream.
--
-- Grain:
--   dim_date       : one row per calendar date
--   dim_customer   : one row per customer_unique_id (person)
--   dim_product    : one row per product_id
--   dim_seller     : one row per seller_id
--   dim_geo        : one row per zip prefix + UNKNOWN
--   fact_order     : one row per order_id
--   fact_order_item: one row per (order_id, order_item_id)
--   fact_payment   : one row per (order_id, payment_sequential)
--   fact_review    : one selected review per order_id
-- ============================================================

BEGIN;

DROP SCHEMA IF EXISTS dw CASCADE;
CREATE SCHEMA dw;

-- ------------------------------------------------------------
-- 1. DIM_GEO
-- Aggregate valid Brazilian coordinates by postal prefix.
-- Out-of-Brazil coordinates are excluded.
-- UNKNOWN guarantees a valid fallback FK.
-- ------------------------------------------------------------

CREATE TABLE dw.dim_geo AS
SELECT
    g.geolocation_zip_code_prefix AS zip_code_prefix,
    AVG(g.geolocation_lat) AS latitude,
    AVG(g.geolocation_lng) AS longitude,
    MODE() WITHIN GROUP (
        ORDER BY NULLIF(TRIM(g.geolocation_city), '')
    ) AS city,
    MODE() WITHIN GROUP (
        ORDER BY NULLIF(TRIM(g.geolocation_state), '')
    ) AS state,
    COUNT(*)::INTEGER AS source_points,
    FALSE AS is_unknown
FROM raw.geolocation g
WHERE g.geolocation_lat BETWEEN -34.0 AND 6.0
  AND g.geolocation_lng BETWEEN -74.0 AND -34.0
  AND g.geolocation_zip_code_prefix IS NOT NULL
GROUP BY g.geolocation_zip_code_prefix;

INSERT INTO dw.dim_geo (
    zip_code_prefix,
    latitude,
    longitude,
    city,
    state,
    source_points,
    is_unknown
)
VALUES ('UNKNOWN', NULL, NULL, 'Unknown', 'Unknown', 0, TRUE);

ALTER TABLE dw.dim_geo
    ADD CONSTRAINT pk_dim_geo PRIMARY KEY (zip_code_prefix);

-- ------------------------------------------------------------
-- 2. DIM_DATE
-- Continuous calendar from the earliest to latest source date.
-- is_incomplete_month flags partial first/last source months.
-- ------------------------------------------------------------

CREATE TABLE dw.dim_date AS
WITH source_dates AS (
    SELECT order_purchase_timestamp::DATE AS d
    FROM raw.orders
    WHERE order_purchase_timestamp IS NOT NULL

    UNION ALL
    SELECT order_approved_at::DATE
    FROM raw.orders
    WHERE order_approved_at IS NOT NULL

    UNION ALL
    SELECT order_delivered_carrier_date::DATE
    FROM raw.orders
    WHERE order_delivered_carrier_date IS NOT NULL

    UNION ALL
    SELECT order_delivered_customer_date::DATE
    FROM raw.orders
    WHERE order_delivered_customer_date IS NOT NULL

    UNION ALL
    SELECT order_estimated_delivery_date::DATE
    FROM raw.orders
    WHERE order_estimated_delivery_date IS NOT NULL

    UNION ALL
    SELECT shipping_limit_date::DATE
    FROM raw.order_items
    WHERE shipping_limit_date IS NOT NULL

    UNION ALL
    SELECT review_creation_date::DATE
    FROM raw.order_reviews
    WHERE review_creation_date IS NOT NULL

    UNION ALL
    SELECT review_answer_timestamp::DATE
    FROM raw.order_reviews
    WHERE review_answer_timestamp IS NOT NULL
),
bounds AS (
    SELECT MIN(d) AS min_date, MAX(d) AS max_date
    FROM source_dates
),
calendar AS (
    SELECT gs::DATE AS date_key
    FROM bounds b
    CROSS JOIN LATERAL generate_series(
        b.min_date,
        b.max_date,
        INTERVAL '1 day'
    ) AS gs
)
SELECT
    c.date_key,
    EXTRACT(YEAR FROM c.date_key)::INTEGER AS year,
    EXTRACT(QUARTER FROM c.date_key)::INTEGER AS quarter,
    EXTRACT(MONTH FROM c.date_key)::INTEGER AS month,
    TRIM(TO_CHAR(c.date_key, 'Month')) AS month_name,
    EXTRACT(DAY FROM c.date_key)::INTEGER AS day_of_month,
    EXTRACT(ISODOW FROM c.date_key)::INTEGER AS day_of_week,
    TRIM(TO_CHAR(c.date_key, 'Day')) AS day_name,
    EXTRACT(ISODOW FROM c.date_key) IN (6, 7) AS is_weekend,
    DATE_TRUNC('month', c.date_key)::DATE AS month_start,
    (
        DATE_TRUNC('month', c.date_key)
        + INTERVAL '1 month - 1 day'
    )::DATE AS month_end,
    (
        DATE_TRUNC('month', c.date_key)::DATE
            = DATE_TRUNC('month', b.min_date)::DATE
        AND b.min_date <> DATE_TRUNC('month', b.min_date)::DATE
    )
    OR
    (
        DATE_TRUNC('month', c.date_key)::DATE
            = DATE_TRUNC('month', b.max_date)::DATE
        AND b.max_date <>
            (
                DATE_TRUNC('month', b.max_date)
                + INTERVAL '1 month - 1 day'
            )::DATE
    ) AS is_incomplete_month
FROM calendar c
CROSS JOIN bounds b;

ALTER TABLE dw.dim_date
    ADD CONSTRAINT pk_dim_date PRIMARY KEY (date_key);

-- ------------------------------------------------------------
-- 3. DIM_CUSTOMER
-- One row per person, not per customer_id.
-- SCD Type 1: use attributes from the most recent observed order.
-- If the postal prefix has no valid geo row, use UNKNOWN.
-- ------------------------------------------------------------

CREATE TABLE dw.dim_customer AS
WITH observations AS (
    SELECT
        c.customer_unique_id,
        c.customer_id,
        c.customer_zip_code_prefix,
        c.customer_city,
        c.customer_state,
        o.order_purchase_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY c.customer_unique_id
            ORDER BY
                o.order_purchase_timestamp DESC NULLS LAST,
                c.customer_id DESC
        ) AS rn
    FROM raw.customers c
    LEFT JOIN raw.orders o
        ON o.customer_id = c.customer_id
)
SELECT
    x.customer_unique_id,
    x.customer_id AS latest_customer_id,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM dw.dim_geo g
            WHERE g.zip_code_prefix = x.customer_zip_code_prefix
        )
        THEN x.customer_zip_code_prefix
        ELSE 'UNKNOWN'
    END AS zip_code_prefix,
    x.customer_city AS city,
    x.customer_state AS state,
    x.order_purchase_timestamp AS latest_observed_at
FROM observations x
WHERE x.rn = 1;

ALTER TABLE dw.dim_customer
    ADD CONSTRAINT pk_dim_customer
    PRIMARY KEY (customer_unique_id);

-- ------------------------------------------------------------
-- 4. DIM_PRODUCT
-- Correct warehouse column names; preserve original source names.
-- English category falls back to the source category, then Unknown.
-- ------------------------------------------------------------

CREATE TABLE dw.dim_product AS
SELECT
    p.product_id,
    COALESCE(
        NULLIF(TRIM(t.product_category_name_english), ''),
        NULLIF(TRIM(p.product_category_name), ''),
        'Unknown'
    ) AS product_category_english,
    p.product_category_name AS source_category_name,
    p.product_name_lenght::INTEGER AS product_name_length,
    p.product_description_lenght::INTEGER AS product_description_length,
    p.product_photos_qty::INTEGER AS product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm
FROM raw.products p
LEFT JOIN raw.category_translation t
    ON t.product_category_name = p.product_category_name;

ALTER TABLE dw.dim_product
    ADD CONSTRAINT pk_dim_product PRIMARY KEY (product_id);

-- ------------------------------------------------------------
-- 5. DIM_SELLER
-- ------------------------------------------------------------

CREATE TABLE dw.dim_seller AS
SELECT
    s.seller_id,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM dw.dim_geo g
            WHERE g.zip_code_prefix = s.seller_zip_code_prefix
        )
        THEN s.seller_zip_code_prefix
        ELSE 'UNKNOWN'
    END AS zip_code_prefix,
    s.seller_city AS city,
    s.seller_state AS state
FROM raw.sellers s;

ALTER TABLE dw.dim_seller
    ADD CONSTRAINT pk_dim_seller PRIMARY KEY (seller_id);

-- ------------------------------------------------------------
-- 6. FACT_ORDER
-- One row for every order, including missing items/payments.
-- is_late is NULL unless delivered and estimated dates are known.
-- Late calculation uses calendar dates, not timestamp precision.
-- ------------------------------------------------------------

CREATE TABLE dw.fact_order AS
SELECT
    o.order_id,
    c.customer_unique_id,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM dw.dim_geo g
            WHERE g.zip_code_prefix = c.customer_zip_code_prefix
        )
        THEN c.customer_zip_code_prefix
        ELSE 'UNKNOWN'
    END AS customer_zip_code_prefix,

    o.order_status,

    o.order_purchase_timestamp::DATE AS purchase_date_key,
    o.order_approved_at::DATE AS approved_date_key,
    o.order_delivered_carrier_date::DATE AS carrier_date_key,
    o.order_delivered_customer_date::DATE AS delivered_date_key,
    o.order_estimated_delivery_date::DATE AS estimated_delivery_date_key,

    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,

    CASE
        WHEN o.order_status <> 'delivered'
          OR o.order_delivered_customer_date IS NULL
          OR o.order_estimated_delivery_date IS NULL
        THEN NULL
        ELSE
            o.order_delivered_customer_date::DATE
            > o.order_estimated_delivery_date::DATE
    END AS is_late,

    EXISTS (
        SELECT 1
        FROM raw.order_items i
        WHERE i.order_id = o.order_id
    ) AS has_items,

    EXISTS (
        SELECT 1
        FROM raw.order_payments p
        WHERE p.order_id = o.order_id
    ) AS has_payments

FROM raw.orders o
JOIN raw.customers c
    ON c.customer_id = o.customer_id;

ALTER TABLE dw.fact_order
    ADD CONSTRAINT pk_fact_order PRIMARY KEY (order_id);

-- ------------------------------------------------------------
-- 7. FACT_ORDER_ITEM
-- Grain: (order_id, order_item_id)
-- ------------------------------------------------------------

CREATE TABLE dw.fact_order_item AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM dw.dim_geo g
            WHERE g.zip_code_prefix = s.seller_zip_code_prefix
        )
        THEN s.seller_zip_code_prefix
        ELSE 'UNKNOWN'
    END AS seller_zip_code_prefix,
    i.shipping_limit_date::DATE AS shipping_limit_date_key,
    i.shipping_limit_date,
    i.price,
    i.freight_value
FROM raw.order_items i
LEFT JOIN raw.sellers s
    ON s.seller_id = i.seller_id;

ALTER TABLE dw.fact_order_item
    ADD CONSTRAINT pk_fact_order_item
    PRIMARY KEY (order_id, order_item_id);

-- ------------------------------------------------------------
-- 8. FACT_PAYMENT
-- Grain: (order_id, payment_sequential)
-- ------------------------------------------------------------

CREATE TABLE dw.fact_payment AS
SELECT
    p.order_id,
    p.payment_sequential,
    p.payment_type,
    p.payment_installments::INTEGER AS payment_installments,
    p.payment_value
FROM raw.order_payments p;

ALTER TABLE dw.fact_payment
    ADD CONSTRAINT pk_fact_payment
    PRIMARY KEY (order_id, payment_sequential);

-- ------------------------------------------------------------
-- 9. FACT_REVIEW
-- One review per order.
-- Policy: latest creation date, then latest answer timestamp,
-- then review_id as deterministic tie-breaker.
-- review_count preserves source review count per order.
-- ------------------------------------------------------------

CREATE TABLE dw.fact_review AS
WITH review_counts AS (
    SELECT
        order_id,
        COUNT(*)::INTEGER AS review_count
    FROM raw.order_reviews
    GROUP BY order_id
),
ranked_reviews AS (
    SELECT
        r.*,
        ROW_NUMBER() OVER (
            PARTITION BY r.order_id
            ORDER BY
                r.review_creation_date DESC NULLS LAST,
                r.review_answer_timestamp DESC NULLS LAST,
                r.review_id DESC
        ) AS rn
    FROM raw.order_reviews r
)
SELECT
    r.order_id,
    r.review_id AS selected_review_id,
    rc.review_count,
    r.review_score::INTEGER AS review_score,
    r.review_comment_title,
    r.review_comment_message,
    r.review_creation_date::DATE AS review_creation_date_key,
    r.review_answer_timestamp::DATE AS review_answer_date_key,
    r.review_creation_date,
    r.review_answer_timestamp
FROM ranked_reviews r
JOIN review_counts rc
    ON rc.order_id = r.order_id
WHERE r.rn = 1;

ALTER TABLE dw.fact_review
    ADD CONSTRAINT pk_fact_review PRIMARY KEY (order_id);

-- ------------------------------------------------------------
-- 10. FOREIGN KEYS
-- Install actual PostgreSQL constraints.
-- ------------------------------------------------------------

ALTER TABLE dw.dim_customer
    ADD CONSTRAINT fk_dim_customer_geo
    FOREIGN KEY (zip_code_prefix)
    REFERENCES dw.dim_geo (zip_code_prefix);

ALTER TABLE dw.dim_seller
    ADD CONSTRAINT fk_dim_seller_geo
    FOREIGN KEY (zip_code_prefix)
    REFERENCES dw.dim_geo (zip_code_prefix);

ALTER TABLE dw.fact_order
    ADD CONSTRAINT fk_fact_order_customer
    FOREIGN KEY (customer_unique_id)
    REFERENCES dw.dim_customer (customer_unique_id),

    ADD CONSTRAINT fk_fact_order_customer_geo
    FOREIGN KEY (customer_zip_code_prefix)
    REFERENCES dw.dim_geo (zip_code_prefix),

    ADD CONSTRAINT fk_fact_order_purchase_date
    FOREIGN KEY (purchase_date_key)
    REFERENCES dw.dim_date (date_key),

    ADD CONSTRAINT fk_fact_order_approved_date
    FOREIGN KEY (approved_date_key)
    REFERENCES dw.dim_date (date_key),

    ADD CONSTRAINT fk_fact_order_carrier_date
    FOREIGN KEY (carrier_date_key)
    REFERENCES dw.dim_date (date_key),

    ADD CONSTRAINT fk_fact_order_delivered_date
    FOREIGN KEY (delivered_date_key)
    REFERENCES dw.dim_date (date_key),

    ADD CONSTRAINT fk_fact_order_estimated_date
    FOREIGN KEY (estimated_delivery_date_key)
    REFERENCES dw.dim_date (date_key);

ALTER TABLE dw.fact_order_item
    ADD CONSTRAINT fk_fact_item_order
    FOREIGN KEY (order_id)
    REFERENCES dw.fact_order (order_id),

    ADD CONSTRAINT fk_fact_item_product
    FOREIGN KEY (product_id)
    REFERENCES dw.dim_product (product_id),

    ADD CONSTRAINT fk_fact_item_seller
    FOREIGN KEY (seller_id)
    REFERENCES dw.dim_seller (seller_id),

    ADD CONSTRAINT fk_fact_item_seller_geo
    FOREIGN KEY (seller_zip_code_prefix)
    REFERENCES dw.dim_geo (zip_code_prefix),

    ADD CONSTRAINT fk_fact_item_shipping_date
    FOREIGN KEY (shipping_limit_date_key)
    REFERENCES dw.dim_date (date_key);

ALTER TABLE dw.fact_payment
    ADD CONSTRAINT fk_fact_payment_order
    FOREIGN KEY (order_id)
    REFERENCES dw.fact_order (order_id);

ALTER TABLE dw.fact_review
    ADD CONSTRAINT fk_fact_review_order
    FOREIGN KEY (order_id)
    REFERENCES dw.fact_order (order_id),

    ADD CONSTRAINT fk_fact_review_creation_date
    FOREIGN KEY (review_creation_date_key)
    REFERENCES dw.dim_date (date_key),

    ADD CONSTRAINT fk_fact_review_answer_date
    FOREIGN KEY (review_answer_date_key)
    REFERENCES dw.dim_date (date_key);

-- ------------------------------------------------------------
-- 11. INDEXES
-- ------------------------------------------------------------

CREATE INDEX idx_fact_order_customer
    ON dw.fact_order (customer_unique_id);

CREATE INDEX idx_fact_order_purchase_date
    ON dw.fact_order (purchase_date_key);

CREATE INDEX idx_fact_order_item_product
    ON dw.fact_order_item (product_id);

CREATE INDEX idx_fact_order_item_seller
    ON dw.fact_order_item (seller_id);

CREATE INDEX idx_fact_payment_order
    ON dw.fact_payment (order_id);

CREATE INDEX idx_fact_review_score
    ON dw.fact_review (review_score);

-- Update planner statistics.
ANALYZE dw.dim_geo;
ANALYZE dw.dim_date;
ANALYZE dw.dim_customer;
ANALYZE dw.dim_product;
ANALYZE dw.dim_seller;
ANALYZE dw.fact_order;
ANALYZE dw.fact_order_item;
ANALYZE dw.fact_payment;
ANALYZE dw.fact_review;

COMMIT;
