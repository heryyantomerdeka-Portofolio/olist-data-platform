# Olist Data Platform — Data Contract

**Project:** Olist Data Platform  
**Dataset:** Brazilian E-Commerce Public Dataset by Olist  
**Scope:** T0 — Data Profiling, Validation, and Contract Definition  
**Source:** Kaggle — `olistbr/brazilian-ecommerce`  
**Status:** Draft — contract and profiling findings consolidated  
**Version:** 1.0

---

## 1. Purpose

This document defines the expected structure, data types, keys, data-quality rules, measured data-quality findings, and remediation policies for the nine source CSV files used in the Olist Data Platform project.

This contract is the reference for:

1. Bronze ingestion and raw-data preservation.
2. Silver-layer cleaning, type casting, validation, and quarantine.
3. Referential-integrity checks between related datasets.
4. Kafka event processing and replay safety.
5. Data warehouse dimensional modeling.
6. Analytical marts, dashboards, and business reporting.

The source data must be preserved in its original form. Data-quality corrections must be traceable and must not silently overwrite original values.

## 2. Data Contract Principles

- **Preserve raw data:** Bronze stores source data and ingestion metadata without silently modifying business values.
- **Make transformations reproducible:** Silver transformations must be deterministic and documented.
- **Do not silently delete records:** Invalid or unresolved records must be retained, quarantined, or explicitly handled according to a documented rule.
- **Use appropriate data types:** Identifiers and postal codes are strings, dates are timestamps, and financial values use exact numeric types.
- **Distinguish business entities:** `customer_id` identifies a customer record associated with an order, while `customer_unique_id` represents customer identity for person-level analysis.
- **Preserve source values:** Portuguese product-category names remain unchanged even when English translations are unavailable.
- **Validate relationships:** Foreign-key checks identify orphan records without silently removing them.
- **Support idempotency:** Reprocessing the same source data or replaying Kafka events must not create unintended duplicate business records.
- **Record quality outcomes:** Every failed rule must include the dataset, rule, affected count, severity, action, and processing stage.
- **Separate observations from decisions:** A profiling finding is not automatically a data error or a reason to reject a record.

## 3. Source Dataset Inventory

The following counts are expected source baselines. Confirm them against the actual CSV files before enforcing automated assertions.

| # | Source file | Target table | Expected rows | Business key |
|---:|---|---|---:|---|
| 1 | `olist_orders_dataset.csv` | `orders` | 99,441 | `order_id` |
| 2 | `olist_order_items_dataset.csv` | `order_items` | 112,650 | `order_id`, `order_item_id` |
| 3 | `olist_order_payments_dataset.csv` | `order_payments` | 103,886 | `order_id`, `payment_sequential` |
| 4 | `olist_order_reviews_dataset.csv` | `order_reviews` | 99,224 | Under investigation |
| 5 | `olist_customers_dataset.csv` | `customers` | 99,441 | `customer_id` |
| 6 | `olist_sellers_dataset.csv` | `sellers` | 3,095 | `seller_id` |
| 7 | `olist_products_dataset.csv` | `products` | 32,951 | `product_id` |
| 8 | `olist_geolocation_dataset.csv` | `geolocation` | 1,000,163 | No unique business key established |
| 9 | `product_category_name_translation.csv` | `category_translation` | 71 | `product_category_name` |

**Rule:** A row-count mismatch triggers investigation. It must not automatically delete records or reject an entire dataset.

## 4. Table Contracts

### 4.1 Orders

**Source:** `olist_orders_dataset.csv`  
**Expected rows:** 99,441  
**Business key:** `order_id`

| Column | Target type | Rule |
|---|---|---|
| `order_id` | VARCHAR | Required and unique |
| `customer_id` | VARCHAR | Required; references `customers.customer_id` |
| `order_status` | VARCHAR | Required; validate against observed source values |
| `order_purchase_timestamp` | TIMESTAMP | Required and parseable |
| `order_approved_at` | TIMESTAMP | Nullable; parseable when present |
| `order_delivered_carrier_date` | TIMESTAMP | Nullable; parseable when present |
| `order_delivered_customer_date` | TIMESTAMP | Nullable; parseable when present |
| `order_estimated_delivery_date` | TIMESTAMP | Nullable; parseable when present |

**Rules**

- `order_id` must not be null or duplicated.
- Every `customer_id` must reference an existing customer.
- Missing delivery and approval timestamps must be evaluated against `order_status`.
- Chronological anomalies must be flagged for investigation.
- Orders without items or payments must remain available for reconciliation and operational analysis.
- Late deliveries are performance outcomes, not automatically corrupt records.

### 4.2 Order Items

**Source:** `olist_order_items_dataset.csv`  
**Expected rows:** 112,650  
**Business key:** (`order_id`, `order_item_id`)

| Column | Target type | Rule |
|---|---|---|
| `order_id` | VARCHAR | Required; references `orders.order_id` |
| `order_item_id` | INTEGER | Required within an order |
| `product_id` | VARCHAR | Required; references `products.product_id` |
| `seller_id` | VARCHAR | Required; references `sellers.seller_id` |
| `shipping_limit_date` | TIMESTAMP | Required and parseable |
| `price` | DECIMAL(12,2) | Required, parseable, and non-negative |
| `freight_value` | DECIMAL(12,2) | Required, parseable, and non-negative |

**Rules**

- (`order_id`, `order_item_id`) must be unique.
- Each item must reference an existing order, product, and seller.
- Financial values must use exact numeric types rather than floating-point types for reconciliation.
- Negative or malformed monetary values must be quarantined or explicitly classified.
- Zero freight is a soft warning, not an automatic rejection.
- Item price and freight must remain separate fields.

### 4.3 Order Payments

**Source:** `olist_order_payments_dataset.csv`  
**Expected rows:** 103,886  
**Business key:** (`order_id`, `payment_sequential`)

| Column | Target type | Rule |
|---|---|---|
| `order_id` | VARCHAR | Required; references `orders.order_id` |
| `payment_sequential` | INTEGER | Required within an order |
| `payment_type` | VARCHAR | Required; validate against observed values |
| `payment_installments` | INTEGER | Required and parseable |
| `payment_value` | DECIMAL(12,2) | Required, parseable, and non-negative |

**Rules**

- (`order_id`, `payment_sequential`) must be unique.
- An order can contain multiple payment records.
- Aggregate payment records at order level before comparing totals.
- Do not invent payment records for orders without payments.
- Evaluate zero payment separately from a missing payment record.

### 4.4 Order Reviews

**Source:** `olist_order_reviews_dataset.csv`  
**Expected rows:** 99,224  
**Business grain:** Review source record; final analytical grain must be explicitly defined.  
**Candidate composite key:** (`review_id`, `order_id`)

| Column | Target type | Rule |
|---|---|---|
| `review_id` | VARCHAR | Requiredness and uniqueness must be profiled |
| `order_id` | VARCHAR | Required; references `orders.order_id` |
| `review_score` | SMALLINT | Validate expected score range of 1–5 |
| `review_comment_title` | TEXT | Nullable; preserve missing values |
| `review_comment_message` | TEXT | Nullable; preserve missing values |
| `review_creation_date` | TIMESTAMP | Required and parseable |
| `review_answer_timestamp` | TIMESTAMP | Nullable; parseable when present |

**Rules**

- Do not treat `review_id` alone as a guaranteed unique key.
- Preserve the original review record and generate a technical `source_row_id` during ingestion if needed.
- Investigate duplicates using `review_id`, `order_id`, timestamps, score, and comment fields.
- Do not automatically remove all records belonging to duplicated `review_id` groups.
- If no reliable business key can be established, retain source-row identity and document the limitation.
- Missing comments are not automatically invalid.
- If the downstream analytical fact requires one review per order, select the applicable review using a deterministic, documented rule.
- A deduplicated analytical view must not overwrite the raw review records.

### 4.5 Customers

**Source:** `olist_customers_dataset.csv`  
**Expected rows:** 99,441  
**Business key:** `customer_id`

| Column | Target type | Rule |
|---|---|---|
| `customer_id` | VARCHAR | Required and unique |
| `customer_unique_id` | VARCHAR | Required for person-level identity analysis |
| `customer_zip_code_prefix` | VARCHAR | Preserve leading zeros |
| `customer_city` | VARCHAR | Text; normalize only in a derived field |
| `customer_state` | CHAR(2) or VARCHAR | Validate observed source values |

**Rules**

- `customer_id` identifies the customer record associated with an order.
- `customer_unique_id` represents customer identity for repeat-purchase analysis.
- Do not treat the number of distinct `customer_id` values as the number of distinct people.
- Postal codes must remain strings.
- Do not merge customer records solely because their city or postal code matches.

**Reference metric:** Approximately 96,096 distinct people by `customer_unique_id`. Recalculate against the actual source data.

### 4.6 Sellers

**Source:** `olist_sellers_dataset.csv`  
**Expected rows:** 3,095  
**Business key:** `seller_id`

| Column | Target type | Rule |
|---|---|---|
| `seller_id` | VARCHAR | Required and unique |
| `seller_zip_code_prefix` | VARCHAR | Preserve leading zeros |
| `seller_city` | VARCHAR | Text; preserve source value |
| `seller_state` | CHAR(2) or VARCHAR | Validate observed source values |

**Rules**

- `seller_id` must be unique and non-null.
- Seller references in `order_items` must resolve to this table.
- Postal codes must be strings, not integers.
- City and state normalization must not overwrite original values.

### 4.7 Products

**Source:** `olist_products_dataset.csv`  
**Expected rows:** 32,951  
**Business key:** `product_id`

| Column | Target type | Rule |
|---|---|---|
| `product_id` | VARCHAR | Required and unique |
| `product_category_name` | VARCHAR | Nullable; preserve Portuguese source value |
| `product_name_lenght` | INTEGER | Nullable; preserve original column spelling at ingestion |
| `product_description_lenght` | INTEGER | Nullable; preserve original column spelling at ingestion |
| `product_photos_qty` | INTEGER | Nullable; parseable when present |
| `product_weight_g` | DECIMAL(12,3) | Nullable; parseable and non-negative |
| `product_length_cm` | DECIMAL(12,3) | Nullable; parseable and non-negative |
| `product_height_cm` | DECIMAL(12,3) | Nullable; parseable and non-negative |
| `product_width_cm` | DECIMAL(12,3) | Nullable; parseable and non-negative |

**Rules**

- `product_id` must be unique and non-null.
- Null categories must remain null unless a documented business rule establishes a valid replacement.
- English translations must be joined from `category_translation`, not substituted into the original category column.
- Unmapped categories must be reported and retained.
- Negative or physically implausible measurements must be flagged for investigation.
- Preserve source column names in the raw layer even if standardized names are introduced in Silver.

### 4.8 Geolocation

**Source:** `olist_geolocation_dataset.csv`  
**Expected rows:** 1,000,163  
**Business key:** None established.

| Column | Target type | Rule |
|---|---|---|
| `geolocation_zip_code_prefix` | VARCHAR | Preserve leading zeros |
| `geolocation_lat` | DECIMAL(10,7) | Parseable and geographically validated |
| `geolocation_lng` | DECIMAL(10,7) | Parseable and geographically validated |
| `geolocation_city` | VARCHAR | Text; preserve source value |
| `geolocation_state` | CHAR(2) or VARCHAR | Validate observed source values |

**Rules**

- Repeated postal-code prefixes are expected and are not automatically duplicate errors.
- Profile exact duplicate rows separately from repeated ZIP prefixes.
- Preserve all raw rows and coordinates.
- Exact duplicates may be removed in a derived reference table only under a documented rule.
- Geographic bounds may be used as screening rules, not as definitive proof of invalidity.
- Any curated ZIP lookup must use a documented aggregation or deduplication strategy.
- Do not assume one postal-code prefix maps to exactly one coordinate.

### 4.9 Category Translation

**Source:** `product_category_name_translation.csv`  
**Expected rows:** 71  
**Business key:** `product_category_name`

| Column | Target type | Rule |
|---|---|---|
| `product_category_name` | VARCHAR | Required and unique |
| `product_category_name_english` | VARCHAR | Required and parseable as text |

**Rules**

- Validate uniqueness and nullability of `product_category_name`.
- Remove a UTF-8 BOM from the parsed header if present, without modifying the original source file.
- Preserve Portuguese category names as the canonical source values.
- Add English translations through a separate field or a derived join.
- Unmapped non-null categories must remain in the product data and be flagged.
- Do not fabricate English translations for missing mappings.

## 5. T0 Data Quality Findings and Decisions

The following results are measured findings from the current profiling and validation run. They should be regenerated from the raw dataset to confirm reproducibility.

### 5.1 Review Key and Grain

| Check | Measured result | Severity / decision |
|---|---:|---|
| Rows participating in duplicate `review_id` groups | 1,603 | Soft warning; investigate grain |
| Extra occurrences of `review_id` | 814 | Preserve raw; do not blindly deduplicate |
| Rows participating in duplicate review `order_id` groups | 1,098 | Multiple review records may exist per order |
| Extra occurrences of review `order_id` | 551 | Preserve raw records |
| Duplicate composite (`review_id`, `order_id`) | 0 | Candidate composite key passes measured uniqueness check |

**Decision:** The composite key passes the current uniqueness test, but uniqueness alone does not prove it is the correct business key. Continue investigating the review grain and validate requiredness and other constraints before finalizing the contract.

If the downstream review fact requires one record per order, apply a deterministic business rule, such as selecting the latest applicable review timestamp. Document that rule and retain the raw records.

### 5.2 Referential Integrity and Completeness

| Check | Count | Severity / decision |
|---|---:|---|
| Orders without order items | 775 | Soft warning; preserve and investigate |
| Orders without payment records | 1 | Soft warning; do not infer payment |
| Unmapped non-null product categories | 13 | Soft warning; preserve source category |
| Products with null category | 610 | Soft warning; preserve null and expose a quality flag |

The following foreign-key checks passed in the current validation run:

- `orders.customer_id` → `customers.customer_id`
- `order_items.order_id` → `orders.order_id`
- `order_items.product_id` → `products.product_id`
- `order_items.seller_id` → `sellers.seller_id`
- `order_payments.order_id` → `orders.order_id`
- `order_reviews.order_id` → `orders.order_id`

These results describe the relationships tested in the current run. Revalidate them when the source data or transformation logic changes.

### 5.3 Numeric Checks

| Column | Finding | Severity / decision |
|---|---|---|
| `order_items.price` | 0 malformed, 0 negative, 0 zero | Pass measured checks |
| `order_items.freight_value` | 383 zero values | Soft warning; zero is not automatically invalid |
| `order_payments.payment_value` | 9 zero values | Soft warning; investigate context |
| `products.product_weight_g` | 4 zero values | Soft warning; investigate product records |
| `products.product_length_cm` | 0 zero values | Pass zero-value check |
| `products.product_height_cm` | 0 zero values | Pass zero-value check |
| `products.product_width_cm` | 0 zero values | Pass zero-value check |

No malformed or negative values were found in the listed numeric checks.

**Decision:** Preserve zero values unless a documented business rule establishes that they are invalid. Do not infer missing amounts or replace zero values without evidence.

### 5.4 Timestamp Checks

| Check | Count | Severity / decision |
|---|---:|---|
| Approval before purchase | 0 | Pass |
| Carrier handoff before purchase | 166 | Soft warning; validate timestamp ordering |
| Delivery before carrier handoff | 23 | Soft warning; investigate chronology |
| Delivery before purchase | 0 | Pass |
| Delivery after estimated date | 7,827 | Operational performance metric |

**Decision:**

- Keep source timestamps unchanged.
- Investigate the 166 carrier-handoff anomalies and 23 delivery-order anomalies.
- Do not classify late delivery as corrupted data solely because it occurred after the estimated date.
- Any correction or exclusion must be implemented in a documented downstream transformation.

### 5.5 Geolocation Checks

| Check | Count | Severity / decision |
|---|---:|---|
| Exact duplicate rows | 261,831 | Preserve raw; consider deduplication in a derived reference table |
| Invalid latitude parsing | 0 | Pass |
| Invalid longitude parsing | 0 | Pass |
| Coordinates outside approximate Brazil bounds | 11,687 | Soft warning; geographic validation required |
| Distinct ZIP prefixes | 19,015 | Preserve prefixes as text |

**Decision:**

- Approximate Brazil bounds are a screening rule, not definitive proof that a coordinate is invalid.
- Investigate out-of-bounds coordinates before quarantining them.
- Preserve repeated ZIP prefixes because they are expected in the source.
- Deduplicate exact rows only in a derived dataset when justified by the downstream use case.

### 5.6 Item-to-Payment Reconciliation

The current reconciliation compares the order-level sum of item price plus freight with the order-level sum of payment values.

| Check | Count |
|---|---:|
| Comparable orders | 98,665 |
| Absolute difference greater than 0.01 | 380 |
| Absolute difference greater than 1.00 | 249 |
| Orders missing item totals | 775 |
| Orders missing payment totals | 1 |

**Decision:**

- Aggregate items and payments independently at order level before joining the totals.
- Use exact decimal arithmetic and a documented rounding tolerance.
- Treat mismatches as reconciliation exceptions, not automatic evidence of fraud.
- Investigate multiple payment methods, installments, cancellations, adjustments, and metric-definition differences.
- Preserve orders with missing totals and expose a reconciliation status rather than inventing values.

**Important:** The reconciliation counts are screening results. They must be regenerated using the final approved SQL logic before being used as formal acceptance assertions.

## 6. Severity Classification and Enforcement

### 6.1 Hard Failures

Hard failures block progression to the next processing stage when a critical contract is violated.

Examples:

- Required primary/business key is null.
- A key declared unique contains duplicates, unless an explicit exception is approved.
- Required fields cannot be parsed into their target types.
- A critical structural requirement is violated.
- A mandatory stage cannot preserve or trace source records.

A hard failure must identify the dataset, rule, affected count, and processing stage. It must not automatically delete the offending records.

### 6.2 Soft Warnings

Soft warnings allow processing to continue when the issue is documented and the downstream impact is understood.

Examples:

- Zero freight or payment values.
- Missing optional timestamps.
- Orders without items or payments.
- Unmapped product categories.
- Late deliveries.
- Timestamp-order anomalies requiring investigation.
- Geolocation coordinates outside screening bounds.
- Item-to-payment reconciliation differences.

The severity of a finding may be upgraded if later investigation establishes a critical business impact.

### 6.3 Quarantine Policy

Quarantine is appropriate when a record violates an approved rule and cannot safely be used in the target dataset.

Each quarantined record must retain sufficient metadata to trace it back to its source, including:

- Source dataset and source row identifier.
- Original source values or a reference to the immutable raw record.
- Failed rule identifier.
- Failure reason.
- Processing stage and ingestion/run identifier.
- Detection timestamp.
- Remediation status, when applicable.

Do not quarantine records solely because they match a screening signal that has not been confirmed as invalid.

## 7. Implementation and Remediation Policy

| Stage | Responsibility | Required behavior |
|---|---|---|
| T0 — Profiling and contract | Establish expected schema, keys, constraints, and quality findings | Generate reproducible reports and document decisions |
| T1 — Bronze ingestion | Preserve raw source data and ingestion metadata | Immutable source objects, manifests, checksums, and ingestion/run tracking |
| T2 — Silver transformation | Cast types, validate contracts, and produce curated datasets | Deterministic transformations, data-quality results, and traceable quarantine |
| Kafka processing | Process and replay events safely | Idempotent handling, duplicate protection, and explicit handling of out-of-order or invalid events |
| Data warehouse | Model validated business entities and measures | Correct grain, dimensional relationships, and documented metric definitions |
| Analytical marts | Publish reporting-ready datasets | Reconciled metrics, clear definitions, and documented exclusions |

### 7.1 Bronze Requirements

- Preserve the original CSV content.
- Record source filename, checksum, ingestion timestamp, and source/version metadata.
- Use append-only ingestion manifests.
- Do not perform business-level deduplication in Bronze.
- Ensure repeated ingestion is identifiable and traceable.

### 7.2 Silver Requirements

- Apply documented type casting and validation.
- Preserve source values in Bronze and retain lineage to the original record.
- Separate accepted, warned, and quarantined outcomes.
- Implement deterministic transformations.
- Make deduplication policies explicit for reviews and geolocation.
- Preserve unmapped categories and nullable fields where permitted.
- Record counts and reasons for each failed rule.

### 7.3 Kafka Requirements

- Replaying the same event must not create unintended duplicate business records.
- Define event identity and deduplication strategy for each event type.
- Handle duplicate and out-of-order events explicitly.
- Preserve invalid-event details for investigation.
- Distinguish transport/event processing failures from business-data validation failures.

### 7.4 Warehouse and Mart Requirements

- Define the grain of each fact table before loading.
- Avoid double-counting item and payment totals when joining datasets with different grains.
- Keep customer-record identity distinct from person-level identity.
- Document how reviews are represented if several review records exist for one order.
- Define reconciliation tolerances and reporting exclusions.
- Make the lineage from raw source to published metric traceable.

## 8. Data Quality Results Log

Each validation run should generate a structured result with at least these fields:

| Field | Description |
|---|---|
| `run_id` | Unique identifier for the validation run |
| `dataset` | Source or target dataset |
| `rule_id` | Stable identifier for the rule |
| `rule_name` | Human-readable rule description |
| `severity` | `HARD_FAILURE` or `SOFT_WARNING` |
| `affected_count` | Number of affected records |
| `action` | `PASS`, `WARN`, `QUARANTINE`, or `BLOCK` |
| `stage` | Pipeline stage where the rule was evaluated |
| `executed_at` | Timestamp of rule execution |
| `details` | Additional diagnostics and remediation context |

Use stable rule identifiers, for example:

- `ORDERS_PK_001` — `order_id` required and unique.
- `ORDER_ITEMS_PK_001` — (`order_id`, `order_item_id`) unique.
- `PAYMENTS_PK_001` — (`order_id`, `payment_sequential`) unique.
- `REVIEWS_GRAIN_001` — review grain and candidate key validation.
- `ORDERS_FK_001` — order customer reference integrity.
- `PRODUCT_CATEGORY_001` — category mapping coverage.
- `GEO_BOUNDS_001` — geolocation screening.
- `ORDER_RECON_001` — item-to-payment reconciliation.

These identifiers are proposed naming conventions; the implementation must use them consistently.

## 9. T0 Acceptance Criteria

T0 can be considered complete when the following conditions are satisfied:

- [ ] All nine source CSV files have been identified and profiled.
- [ ] Actual row counts are recorded and compared with expected baselines.
- [ ] Source schemas and target data types are documented.
- [ ] Business keys and table grain are documented, including the review-table limitation.
- [ ] Primary-key, required-field, and foreign-key validations are reproducible.
- [ ] Numeric and timestamp checks have been executed.
- [ ] Geolocation duplicates and geographic screening results are documented.
- [ ] Item-to-payment reconciliation is reproducible and its metric definition is recorded.
- [ ] Every known issue has a severity, decision, and downstream action.
- [ ] Raw data remains preserved, and no unapproved records have been silently deleted.
- [ ] The profiling report can be regenerated from the original source files.
- [ ] The contract is aligned with the actual validation and Silver implementation.

Passing the listed checks does not mean every business question has been resolved. Unresolved findings must remain documented and traceable.

## 10. Open Decisions and Limitations

The following items require confirmation before the contract is treated as fully finalized:

1. **Review grain:** Confirm the intended business grain and whether the candidate composite key remains valid after broader validation.
2. **Review selection:** Define a deterministic rule if downstream reporting requires one review per order.
3. **Geolocation curation:** Define the aggregation or deduplication rule for any derived postal-code lookup.
4. **Geographic screening:** Approve the screening bounds and handling policy before quarantining coordinates.
5. **Reconciliation:** Confirm the final SQL, decimal precision, tolerance, and handling of exceptional order statuses.
6. **Status domains:** Validate allowed order statuses and payment types against the actual source.
7. **Schema enforcement:** Confirm which constraints are hard failures and which permit warnings or quarantine.
8. **Row-count baselines:** Reconfirm the expected counts against the exact raw files used by the pipeline.

## 11. Change Management

- Any change to schema, keys, validation rules, severity, or remediation policy must be documented in this file.
- Changes must include a reason, impact assessment, and validation evidence.
- Profiling findings must be regenerated when source data or validation logic changes.
- The contract and implementation must remain aligned.
- This file is the single source of truth for the Olist Data Platform data contract.

---

**End of Data Contract**
