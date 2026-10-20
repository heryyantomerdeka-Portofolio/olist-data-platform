# Olist Data Platform

An end-to-end e-commerce data platform built using PostgreSQL, MinIO, Kafka, Python, and Power BI.

Proyek ini mengolah dataset Brazilian E-Commerce Olist dari raw data ingestion hingga analytical data warehouse, data marts, dan Kafka streaming. Fokus proyek adalah membangun pipeline data yang dapat divalidasi, mendokumentasikan kualitas data, dan menguji perilaku sistem dalam beberapa skenario pemrosesan.

## Project Overview

Platform ini mencakup beberapa lapisan pemrosesan data:

- **Bronze:** Menyimpan raw dataset di MinIO beserta manifest dan checksum.
- **Silver:** Memvalidasi dan menyiapkan data untuk proses berikutnya.
- **Data Warehouse:** Menyusun data terstruktur untuk kebutuhan analitik.
- **Data Mart / Gold:** Menyediakan dataset analitik yang siap digunakan.
- **Kafka Streaming:** Memproses order lifecycle events, menangani duplikasi, dan mencatat pesan tidak valid melalui dead-letter queue (DLQ).
- **Power BI:** Menyajikan hasil analitik dalam bentuk dashboard.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Data ingestion, validation, and processing |
| PostgreSQL | Relational storage and analytical data |
| MinIO | Object storage for raw data |
| Apache Kafka | Event streaming |
| SQL | Transformation and analytical modeling |
| Power BI | Data visualization |

## Documentation

- [Runbook](RUNBOOK.md) — environment setup and execution instructions.
- [Evaluation Evidence](EVALUATION_EVIDENCE.md) — validation evidence, metrics, test results, and known limitations.
- [Failure Tests](outputs/failure_tests.md) — documented failure scenarios and recovery tests.
- [Data Contract](DATA_CONTRACT.md) — data structure and validation expectations.

## Implementation Status

The following status reflects the available implementation and validation evidence. It does not imply that every stage is orchestrated through `pipeline.py`.

| Stage | Scope | Current Status |
|---|---|---|
| T0 — Environment | Environment preparation and dataset checks | Supporting artifacts available; pipeline entry point not implemented |
| T1 — Bronze Ingestion | Raw data ingestion into MinIO | Bronze artifacts and validation report available; standalone ingestion script exists, but pipeline entry point is not implemented |
| T2 — Silver | Data validation and preparation | Validation report available |
| T3 — PostgreSQL Load / Streaming | Relational loading and Kafka streaming | Loading and streaming have separate implementation and test evidence |
| T4 — Data Warehouse | Analytical warehouse modeling | Validation report available |
| T5 — Data Mart / Gold | Analytical marts and exports | Six mart exports validated |
| T6 — Streaming Orchestration | Streaming execution and failure scenarios | Supporting scripts and test evidence available; pipeline entry point and failure-scenario validation remain incomplete |

## Data Pipeline

### T0 — Environment and Data Profiling

This stage covers the local development environment, source dataset preparation, and initial data profiling.

Available supporting artifacts include:

- `outputs/profile.md`
- `outputs/key_validation.csv`
- `DATA_CONTRACT.md`

The data contract and validation artifacts document the expected data structure and identified quality concerns.

### T1 — Bronze Ingestion

The Bronze layer stores the original Olist CSV files in MinIO to preserve the source data before downstream transformations.

The standalone ingestion implementation is available at:

- `scripts/ingest_bronze.py`
- `outputs/bronze_report.md`

The Bronze artifacts document nine source tables, object metadata, checksums, and version-related information.

The Bronze layer is intended to provide traceability for the original source data and support downstream validation.

**Implementation note:** The standalone ingestion script and Bronze artifacts are available, but T1 has not yet been integrated as an implemented stage in `pipeline.py`.

### T2 — Silver Data Validation

The Silver stage validates and prepares the source data for downstream processing.

The available evaluation evidence reports:

- Nine source tables processed.
- 1,550,922 rows reported across the Silver tables.
- Zero quarantined rows in the recorded validation run.

These figures represent the documented validation run and should be interpreted within the scope of its recorded checks.

### T3 — PostgreSQL Load and Kafka Streaming

The streaming pipeline publishes order lifecycle events to Kafka and consumes them into PostgreSQL.

The consumer validates incoming messages, handles duplicate event IDs, protects the current order state against stale events, and routes invalid messages to a dead-letter queue.

#### Architecture

1. **Producer:** Generates order lifecycle events from source orders.
2. **Kafka:** Transports events through `olist.order-events`; invalid messages are routed to `olist.order-events.dlq`.
3. **Consumer:** Validates messages, deduplicates events, and applies event-ordering rules.
4. **PostgreSQL:** Stores event history, current order state, DLQ records, and consumer metrics.

#### PostgreSQL Tables

| Table | Purpose |
|---|---|
| `stream.order_events` | Event history with event-ID deduplication |
| `stream.order_current` | Latest accepted status for each order |
| `stream.dlq_messages` | Invalid messages and failure details |
| `stream.consumer_metrics` | Batch-level processing and freshness metrics |

#### Validation Results

The recorded baseline streaming test used a sample of 100 Olist orders.

| Validation | Result |
|---|---:|
| Persisted event history | 380 events |
| Current order states | 100 orders |
| Duplicate event IDs in PostgreSQL | 0 |
| DLQ records | 2 |
| Order statuses matching source | 100/100 |
| Mismatched order statuses | 0 |
| Current orders missing from source | 0 |

**Recorded database validation result: 7/7 checks passed.**

#### Fault Injection and Recovery

A seeded producer test using seed `42` generated:

- 380 base events.
- 16 injected duplicate events.
- 8 delayed events.
- 2 malformed messages.

A separate recovery consumer group replayed the Kafka topic. Previously stored event IDs were ignored, and the two invalid messages were retained in PostgreSQL DLQ storage.

The out-of-order test also confirmed that a late `shipped` event did not overwrite an already accepted `delivered` state.

#### Data Integrity Design

The event-history table uses a unique event ID to prevent duplicate event records at the database layer.

The current-state table applies status-rank and event-timestamp rules to prevent stale or lower-ranked events from replacing the accepted state.

**Scope limitation:** These results cover the documented 100-order test sample, not the complete 99,441-order dataset. The tests demonstrate the behavior of the implemented scenarios; they do not establish distributed exactly-once processing between Kafka and PostgreSQL.

### T4 — Data Warehouse

The Data Warehouse stage organizes validated data for analytical querying.

Validation evidence is documented in the project evaluation materials and the warehouse report.

See `outputs/dw_report.md` for the recorded validation results.

### T5 — Data Mart and Gold Exports

The Data Mart / Gold stage provides analytical datasets for reporting and visualization.

The available evidence records six validated mart exports.

Key artifacts include:

- `outputs/gold/export_validation.csv`
- `outputs/marts_report.md`

These exports provide the basis for downstream analysis and dashboard development.

### T6 — Streaming Orchestration

This stage concerns the orchestration and validation of streaming workflows and their failure scenarios.

Supporting streaming scripts include:

- `streaming_producer.py`
- `streaming_consumer.py`
- `streaming_common.py`

Failure-scenario evidence is documented in `outputs/failure_tests.md`.

**Implementation note:** Supporting scripts and test evidence are available, but the T6 pipeline entry point and complete failure-scenario validation remain unfinished.

## Main Artifacts

| Artifact | Description |
|---|---|
| `outputs/olist-data-platform.pbix` | Power BI dashboard |
| `outputs/bronze_report.md` | Bronze ingestion report |
| `outputs/profile.md` | Initial data profiling |
| `outputs/key_validation.csv` | Key validation results |
| `outputs/dw_report.md` | Data Warehouse validation report |
| `outputs/marts_report.md` | Data Mart report |
| `outputs/gold/export_validation.csv` | Gold export validation |
| `outputs/failure_tests.md` | Failure-scenario test evidence |

## Getting Started

### Prerequisites

- Windows with Docker Desktop.
- Python 3.10 or newer.
- Git.
- The Olist Brazilian E-Commerce dataset.
- The environment configuration and dependencies described in `RUNBOOK.md`.

### 1. Clone the Repository

```bash
git clone https://github.com/heryyantomerdeka-Portofolio/olist-data-platform.git
cd olist-data-platform
```

### 2. Configure Environment Variables

Create a local environment file from the provided template:

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

Edit `.env` and provide the required local credentials and configuration values.

Do not commit `.env` or publish real credentials. Use `.env.example` as the template for the variables required by the project.

### 3. Install Dependencies and Start Services

Follow the environment setup and dependency instructions in [RUNBOOK.md](RUNBOOK.md).

Start Docker services only after configuring the required environment variables.

### 4. Run the Available Pipeline Stages

Review the implementation status and the instructions in `RUNBOOK.md` before running a stage.

Not every stage is currently implemented as an executable `pipeline.py` entry point. Do not assume that all stages can be executed end-to-end through a single command.

## Known Limitations

- T0, T1, and T6 are not fully implemented as pipeline entry points.
- Some stages have separate implementation artifacts and validation evidence rather than complete end-to-end orchestration.
- Streaming reconciliation covers a 100-order sample rather than the entire source dataset.
- The streaming tests do not prove distributed exactly-once processing between Kafka and PostgreSQL.
- Validation results represent the recorded test runs and may not cover every possible data-quality or failure scenario.

## Project Objective

This project demonstrates practical data engineering concepts across raw ingestion, data validation, relational storage, analytical modeling, event streaming, and reporting.

The emphasis is on traceable processing, measurable validation, and transparent documentation of both implemented capabilities and remaining work.
