# StreamLake

> Real-Time Data Lakehouse with ML Feature Store & Unified Query Engine

A production-grade, self-hosted data platform that unifies real-time event ingestion, medallion architecture storage, ML feature serving, and analytics — the same architecture used at Uber, Airbnb, DoorDash, and Stripe.

---

## Architecture

```
                        ┌─────────────────────────────────────────────────────────┐
                        │                  STREAMLAKE ARCHITECTURE                 │
                        └─────────────────────────────────────────────────────────┘

  Python Event              Redpanda Cloud             Schema Registry
  Producer (sim)    ──►    (Kafka-compatible)    ◄───  (Avro schemas)
                                  │
                    ┌─────────────▼──────────────┐
                    │         BRONZE LAYER        │  Raw, immutable events
                    │    Delta Lake on MinIO/S3   │  Partitioned by ingestion_date
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │    PyFlink Streaming Job    │  Event-time watermarks
                    │  + Great Expectations       │  Dedup, type cast, validate
                    │  + Quarantine Router        │  Late event handling
                    └──────┬──────────┬──────────┘
                           │          │
              ┌────────────▼──┐   ┌───▼────────────┐
              │  SILVER LAYER │   │  Quarantine     │  Failed records + alerts
              │  Delta Lake   │   │  Delta Table    │
              └────────┬──────┘   └────────────────┘
                       │
          ┌────────────▼────────────┐
          │   Airflow DAGs          │  Daily batch aggregations
          │   (Astronomer/Docker)   │  DuckDB / Spark compute
          └────────────┬────────────┘
                       │
          ┌────────────▼────────────┐
          │       GOLD LAYER        │  DAU, revenue, churn signals
          │  Delta Lake (Z-ordered) │  Funnel conversion rates
          └──────┬──────────────────┘
                 │
    ┌────────────▼────────────┐
    │   DuckDB / Trino        │  Query engine
    │   Superset / Metabase   │  BI dashboards
    └─────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │                      ML FEATURE STORE                           │
  │                                                                 │
  │  Silver ──► Flink Rolling Windows ──► ┌──────────┐  ┌───────┐ │
  │              (1m / 5m / 1h / 24h)     │  Redis   │  │ Delta │ │
  │                                        │ (online) │  │(offline│ │
  │                                        └────┬─────┘  └───┬───┘ │
  │                                             │             │     │
  │                                       FastAPI        Training   │
  │                                       inference      datasets   │
  │                                       (<10ms p99)   (PIT join)  │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │                         ML LOOP                                 │
  │                                                                 │
  │  Feast offline ──► XGBoost train ──► MLflow registry           │
  │                                           │                     │
  │                              Champion / Challenger (90/10)      │
  │                              FastAPI inference endpoint         │
  │                              SHAP explainability dashboard      │
  │                              PSI drift ──► auto retrain DAG     │
  └─────────────────────────────────────────────────────────────────┘
```

---

## Scale Targets

| Metric | Target | Status |
|--------|--------|--------|
| Ingestion throughput | 1,400+ events/sec sustained | 🔲 |
| End-to-end freshness | < 5 minutes Bronze → Gold | 🔲 |
| Feature serving latency | < 9ms p99 (Redis) | 🔲 |
| Data quality pass rate | 99.6%+ | 🔲 |
| Churn model AUC | 0.91 | 🔲 |
| Drift detection SLA | < 24 hours | 🔲 |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Event Streaming | Redpanda Cloud + Confluent Schema Registry (Avro) |
| Stream Processing | Apache Flink (PyFlink 1.19) |
| Storage | Delta Lake on MinIO (local) / AWS S3 (cloud) |
| Batch Orchestration | Apache Airflow 2.9 (Astronomer Cloud free tier) |
| Data Quality | Great Expectations |
| Query Engine | DuckDB (embedded) + Trino (optional distributed) |
| Feature Store | Feast 0.39 |
| Online Store | Redis 7 |
| ML Tracking | MLflow 2.12 |
| BI Layer | Apache Superset / Metabase |
| Serving API | FastAPI + Uvicorn |
| Monitoring | Grafana + Prometheus |
| Database | PostgreSQL (lineage metadata, A/B results) |

---

## Build Phases

- [x] **Phase 0** — Repo setup, folder structure, Docker Compose skeleton, environment
- [x] **Phase 1** — Event ingestion: Redpanda → Avro Schema Registry → Bronze Delta Lake
- [x] **Phase 2** — Bronze → Silver: watermark tracking, dedup, Great Expectations, quarantine routing
- [ ] **Phase 3** — Silver → Gold: Airflow DAGs, DuckDB aggregations, Superset BI dashboard
- [ ] **Phase 4** — ML Feature Store: Feast + Flink rolling windows + Redis + Delta offline
- [ ] **Phase 5** — ML Loop: XGBoost + MLflow + FastAPI inference + SHAP + A/B testing
- [ ] **Phase 6** — Observability: PSI drift monitoring, Grafana dashboards, Locust load tests

---

## Repository Structure

```
streamlake/
├── ingestion/            # Kafka producer, Avro schemas, Bronze Delta writer
│   └── avro_schemas/     # Avro schema definitions per event type
├── processing/           # PyFlink streaming jobs (Bronze → Silver)
├── storage/              # Delta writers, schema definitions, lineage store
├── quality/              # Great Expectations suites, quarantine router
├── feature_store/        # Feast definitions, Flink feature pipeline, online/offline stores
├── ml/                   # Model training, MLflow, A/B splitter, SHAP, retrain DAG
├── serving/              # FastAPI inference endpoint, feature retriever, drift monitor
├── orchestration/
│   └── dags/             # Airflow DAGs (Gold refresh, quality checks, retraining)
├── infra/
│   ├── grafana/          # Grafana dashboard JSON exports
│   └── prometheus/       # Prometheus scrape config
├── docs/
│   └── diagrams/         # Architecture and data flow diagrams
├── .github/
│   └── workflows/        # GitHub Actions CI
├── docker-compose.yml    # Full local stack (Redpanda, MinIO, Redis, PostgreSQL, Grafana)
├── requirements.txt      # Core Python dependencies
├── requirements-flink.txt    # PyFlink (needs Java 11+)
├── requirements-airflow.txt  # Apache Airflow (heavy, isolated install)
└── requirements-dev.txt  # Dev/test tools
```

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11
- Java 11+ (for PyFlink only)

### 1. Clone and set up environment

```bash
git clone https://github.com/<your-username>/streamlake.git
cd streamlake
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Copy environment variables

```bash
cp .env.example .env
# Edit .env with your Redpanda Cloud credentials
```

### 3. Start the local infrastructure

```bash
docker compose up -d
```

This starts: MinIO, Redis, PostgreSQL, Grafana, Prometheus.

### 4. Verify services

| Service | URL | Credentials |
|---------|-----|-------------|
| MinIO S3 API | http://localhost:9002 | minioadmin / minioadmin |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| Grafana | http://localhost:3000 | admin / admin |
| Redis | localhost:6379 | — |
| PostgreSQL | localhost:5432 | streamlake / streamlake |

---

---

## Phase 1 — Event Ingestion

**Branch:** `feat/phase-1-ingestion`

### What was built

| File | Purpose |
|------|---------|
| [ingestion/avro_schemas/user_event.avsc](ingestion/avro_schemas/user_event.avsc) | Avro schema — 11 fields covering all event types with null-safe unions |
| [ingestion/schema_registry.py](ingestion/schema_registry.py) | Schema registration, AvroSerializer / AvroDeserializer factory |
| [ingestion/kafka_setup.py](ingestion/kafka_setup.py) | One-time topic creation (4 partitions, 7-day retention, lz4 compression) |
| [ingestion/kafka_producer.py](ingestion/kafka_producer.py) | Event simulator — 6 event types, realistic distribution, 2% late events |
| [ingestion/kafka_to_bronze.py](ingestion/kafka_to_bronze.py) | Kafka consumer → Bronze Delta writer, manual offset commit post-write |
| [storage/bronze_schema.py](storage/bronze_schema.py) | PyArrow schema for the Bronze table (event fields + ingestion metadata) |
| [storage/delta_writer.py](storage/delta_writer.py) | Delta write utility with retry logic, MinIO/S3 storage options |

### Running Phase 1 locally

**1. Start infrastructure**
```bash
docker compose up -d
```

**2. Create the Kafka topic**
```bash
source .venv/bin/activate
python -m ingestion.kafka_setup
```

**3. Register the Avro schema**
```bash
python -c "
from ingestion.schema_registry import register_all_schemas
register_all_schemas('http://localhost:8081')
"
```

**4. Start the event producer** (terminal 1)
```bash
python -m ingestion.kafka_producer --rate 1400
```

**5. Start the Bronze writer** (terminal 2)
```bash
python -m ingestion.kafka_to_bronze \
  --table-path s3://streamlake-bronze/events \
  --batch-size 500 \
  --batch-timeout 10
```

**6. Verify Bronze table in MinIO**

Open [http://localhost:9001](http://localhost:9001) → bucket `streamlake-bronze` → you should see Parquet files in `events/ingestion_date=YYYY-MM-DD/` directories.

### Running tests
```bash
pytest tests/ -v
```

---

## Phase 2 — Bronze → Silver Pipeline

### What was built

| File | Purpose |
|------|---------|
| [processing/watermark_config.py](processing/watermark_config.py) | `WatermarkConfig` dataclass — allowed_lateness=5m, max_lateness=1h |
| [processing/late_event_handler.py](processing/late_event_handler.py) | `WatermarkTracker` — classifies events as on_time / late / discard |
| [processing/dedup.py](processing/dedup.py) | `EventDeduplicator` — LRU OrderedDict with TTL eviction (mirrors Flink RocksDB state) |
| [quality/expectations_suite.py](quality/expectations_suite.py) | `SilverValidator` — 6 GE-style expectation types per record |
| [quality/quarantine_router.py](quality/quarantine_router.py) | `QuarantineRouter` — buffers and writes failed records to quarantine Delta table |
| [storage/silver_schema.py](storage/silver_schema.py) | PyArrow schemas for Silver, Quarantine, and Late Events tables |
| [processing/bronze_to_silver.py](processing/bronze_to_silver.py) | Micro-batch pipeline runner (incremental, checkpoint-based) |
| [processing/flink_bronze_to_silver.py](processing/flink_bronze_to_silver.py) | Full PyFlink DataStream API job (for Flink cluster deployment) |
| [verify_silver.py](verify_silver.py) | Standalone verification: watermark stats, event distribution, quality checks |
| [tests/processing/test_dedup.py](tests/processing/test_dedup.py) | Unit tests — deduplication logic |
| [tests/processing/test_watermark.py](tests/processing/test_watermark.py) | Unit tests — watermark classification |
| [tests/quality/test_expectations.py](tests/quality/test_expectations.py) | Unit tests — all 6 expectation types |

### Pipeline design

```
Bronze Delta  ──►  Watermark Tracker  ──►  Deduplicator  ──►  GE Validator
                        │                                           │
                     discard                                      invalid ──► Quarantine Delta
                                                                    │
                                                                  valid ──► Silver Delta
                                                                   (partitioned by event_date)
```

**Key decisions:**
- **Watermark = max_event_ts − 5 minutes**: handles out-of-order events up to 5 min late, discards anything older than 1 hour
- **Dedup keyed on event_id**: LRU dict with 1-hour TTL — mirrors Flink's `ValueState<Long>` with `StateTtlConfig`
- **Checkpoint file** (`.checkpoint/silver_checkpoint.json`): tracks last processed Bronze Delta version so re-runs are incremental
- **PyFlink file** ships with production-ready `KeyedProcessFunction` + `OutputTag` quarantine side-output — ready for Flink cluster deployment

### Running Phase 2 locally

**Prerequisites:** Phase 1 must have run so Bronze Delta has data.

**1. Run the pipeline once**
```bash
source .venv/bin/activate
python -m processing.bronze_to_silver --once
```

Expected output:
```
Pipeline complete | total=4,999 silver=4,999 quarantine=0 late=50 duplicates=0 discarded=0 |
watermark=... | dedup_state_size=4,999
```

**2. Verify Silver table**
```bash
python verify_silver.py
```

**3. Run unit tests**
```bash
pytest tests/ -v   # 58 tests, all pass
```

**4. Continuous mode** (polls Bronze every 15s as new data arrives)
```bash
python -m processing.bronze_to_silver --poll-interval 15
```

### Scale results

| Metric | Result |
|--------|--------|
| Records processed | 5,000 (bounded test run) |
| Throughput | ~4,999/batch in < 2s |
| Late events | ~50 (1% — injected by producer) |
| Quarantine rate | 0% (all synthetic data is valid) |
| Duplicate rate | 0% |
| Tests passing | 58 / 58 |

---

## License

MIT
