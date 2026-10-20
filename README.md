# Olist Data Platform

Platform data e-commerce Olist untuk membangun alur data dari raw ingestion
hingga analytical data warehouse, data marts, dan Kafka streaming.

## Dokumentasi

- [Runbook](RUNBOOK.md) — persiapan environment dan panduan eksekusi.
- [Evaluation Evidence](EVALUATION_EVIDENCE.md) — bukti validasi, metrik,
  hasil pengujian, serta keterbatasan yang diketahui.
- [Failure Tests](outputs/failure_tests.md) — catatan pengujian skenario kegagalan.

## Status Implementasi

| Tahap | Status berdasarkan bukti yang tersedia |
|---|---|
| T0 — Environment | Entry point belum diimplementasikan |
| T1 — Bronze ingestion | Artefak Bronze tersedia; entry point belum diimplementasikan |
| T2 — Silver | Laporan validasi tersedia |
| T3 — PostgreSQL load / streaming | Load PostgreSQL dan pengujian streaming memiliki bukti terpisah |
| T4 — Data Warehouse | Laporan validasi tersedia |
| T5 — Data Mart dan Gold | Enam ekspor mart tervalidasi |
| T6 — Streaming orchestration | Entry point tersedia; validasi failure scenario masih berlangsung |

Status tersebut tidak berarti semua tahap sudah dapat dijalankan melalui
`pipeline.py`. Lihat Evaluation Evidence untuk rincian dan batasan.

## Artefak Utama

- `outputs/olist-data-platform.pbix` — dashboard Power BI.
- `outputs/gold/export_validation.csv` — hasil validasi ekspor Gold.
- `outputs/dw_report.md` — laporan Data Warehouse.
- `outputs/marts_report.md` — laporan Data Mart.
- `outputs/failure_tests.md` — bukti pengujian skenario kegagalan.

---
## T3 — Kafka Streaming \& Data Quality



### Architecture



The streaming pipeline publishes Olist order lifecycle events to Kafka and consumes them into PostgreSQL. The consumer validates incoming messages, stores valid events, maintains the latest order status, and routes invalid messages to a dead-letter queue (DLQ).



**Components**

- **Producer:** Generates order lifecycle events from the source orders table.

- **Kafka:** Transports events through `olist.order-events`; invalid events are routed to `olist.order-events.dlq`.

- **Consumer:** Validates events, deduplicates records, detects out-of-order events, and updates the current order state.

- **PostgreSQL:** Stores event history, current order status, DLQ records, and consumer metrics.



### PostgreSQL Tables



| Table | Purpose |

|---|---|

| `stream.order_events` | Event history with event-ID deduplication |

| `stream.order\_current` | Latest accepted status for each order |

| `stream.dlq\_messages` | Invalid messages and their failure details |

| `stream.consumer\_metrics` | Batch-level processing and freshness metrics |



### Validation Results



| Test | Result |

|---|---|

| Baseline ingestion | 380 events processed from 100 orders |

| Current order state | 100 orders stored |

| Source reconciliation | 100/100 orders matched the source status |

| Duplicate handling | Duplicate event IDs ignored during replay |

| Out-of-order handling | A late `shipped` event did not overwrite `delivered` |

| Invalid-message handling | 2 invalid messages recorded in the DLQ |

| Test-data cleanup | Temporary out-of-order test records removed |



### Fault Injection



A producer run with fault injection enabled used seed `42` and generated:

- 380 base events

- 16 injected duplicates

- 8 delayed events

- 2 malformed messages



A separate recovery consumer group replayed the Kafka topic. Previously stored event IDs were ignored, while the two invalid messages were retained in the DLQ.



### Data Integrity



The current-state table uses event status rank and event timestamp to prevent a lower-ranked or older event from replacing a more advanced accepted status. Event IDs are stored with a uniqueness constraint to make repeated delivery safe at the database layer.



### Current Verified Database Counts



| Table | Rows |

|---|---:|

| `stream.order_events` | 380 |

| `stream.order\_current` | 100 |

| `stream.dlq\_messages` | 2 |



**Note:** These counts reflect the baseline dataset after temporary test-order cleanup. Consumer metrics and DLQ records are intentionally retained for audit and demonstration purposes.



### T3 — Kafka Streaming Validation Results



**Overall result: PASS — 7/7 database validation checks**



The streaming pipeline was tested using a sample of 100 Olist orders.



| Validation | Expected/Actual Result | Status |

|---|---:|---|

| Persisted event history | 380 events | PASS |

| Current order states | 100 orders | PASS |

| Duplicate event IDs in PostgreSQL | 0 | PASS |

| DLQ records | 2 | PASS |

| Order statuses matching source | 100/100 | PASS |

| Mismatched order statuses | 0 | PASS |

| Current orders missing from source | 0 | PASS |



**Additional streaming tests**



- **Duplicate replay:** Reprocessing existing Kafka events did not create additional database event records for already-seen event IDs.

- **Out-of-order delivery:** A late `shipped` event did not overwrite a previously accepted `delivered` state.

- **Fault injection:** The producer generated 16 duplicate events, 8 delayed events, and 2 malformed messages in a seeded test run.

- **Dead-letter queue:** Both malformed messages were recorded in PostgreSQL DLQ storage.

- **Source reconciliation:** All 100 tested current-order statuses matched the corresponding source statuses.



**Data integrity design**



The event-history table uses a unique event ID to make duplicate deliveries safe at the database layer. The current-state table applies status-rank and event-timestamp rules to prevent stale or lower-ranked events from replacing the accepted state.



**Scope limitation:** The source reconciliation result covers the 100-order test sample, not the full 99,441-order dataset. The test demonstrates the implemented behavior for the tested scenarios; it does not establish distributed exactly-once processing between Kafka and PostgreSQL.





