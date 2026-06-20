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
- [ ] **Phase 2** — Bronze → Silver: PyFlink streaming job, Great Expectations, quarantine routing
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

## License

MIT
