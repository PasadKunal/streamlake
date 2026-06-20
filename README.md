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
- [x] **Phase 3** — Silver → Gold: DuckDB aggregations (DAU, revenue, funnel, churn signals), Airflow DAG
- [x] **Phase 4** — ML Feature Store: Feast + DuckDB rolling windows + Redis online + Delta offline
- [x] **Phase 5** — ML Loop: XGBoost + MLflow + FastAPI inference + SHAP + A/B testing
- [x] **Phase 6** — Observability: PSI drift monitoring, Prometheus metrics, Grafana dashboard, Locust load tests

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

## Phase 3 — Silver → Gold Pipeline

### What was built

| File | Purpose |
|------|---------|
| [storage/gold_schema.py](storage/gold_schema.py) | PyArrow schemas for all 4 Gold tables |
| [orchestration/gold_aggregations.py](orchestration/gold_aggregations.py) | Pure DuckDB aggregation functions (no I/O, fully unit-testable) |
| [orchestration/dags/gold_refresh_dag.py](orchestration/dags/gold_refresh_dag.py) | Airflow 2.9 TaskFlow DAG — runs nightly at 02:00 UTC |
| [run_gold_pipeline.py](run_gold_pipeline.py) | Local runner — equivalent to triggering the Airflow DAG |
| [verify_gold.py](verify_gold.py) | Standalone verification: shows all 4 Gold tables |
| [tests/orchestration/test_gold_aggregations.py](tests/orchestration/test_gold_aggregations.py) | 28 unit tests covering all aggregations |

### Gold tables

| Table | Path | Grain | Key Metrics |
|-------|------|-------|-------------|
| DAU | `s3://streamlake-gold/dau` | date × country × device | unique_users, total_sessions |
| Revenue | `s3://streamlake-gold/revenue` | date × country × product | total_revenue_cents, AOV |
| Funnel | `s3://streamlake-gold/funnel` | date × country | view→cart%, cart→purchase% |
| UserSignals | `s3://streamlake-gold/user_signals` | user_id | churn_risk_score (0→1), days_since_last_session |

### Running Phase 3 locally

**1. Run the Gold pipeline** (reads Silver, writes all 4 Gold tables)
```bash
source .venv/bin/activate
python run_gold_pipeline.py
```

Expected output:
```
Silver loaded | version=3 records=4,999
Gold/dau          written | rows=40
Gold/revenue      written | rows=112
Gold/funnel       written | rows=10
Gold/user_signals written | rows=3,940
Gold pipeline complete in 2.4s
```

**2. Verify Gold tables**
```bash
python verify_gold.py
```

**3. Run unit tests**
```bash
pytest tests/orchestration/ -v   # 28 tests, all pass
```

### Scale results

| Table | Rows | Compute time |
|-------|------|-------------|
| DAU | 40 (10 countries × ~4 devices) | < 0.5s |
| Revenue | 112 (purchases by country/product) | < 0.5s |
| Funnel | 10 (per country conversion rates) | < 0.5s |
| UserSignals | 3,940 (one row per active user) | < 0.5s |
| **Total** | **4,102 Gold rows from 4,999 Silver** | **2.4s end-to-end** |

---

## Phase 4 — ML Feature Store

### What was built

| File | Purpose |
|------|---------|
| [feature_store/feature_store.yaml](feature_store/feature_store.yaml) | Feast config — Redis online store, File offline store |
| [feature_store/feature_repo.py](feature_store/feature_repo.py) | Feast entity (`user_id`) + `user_activity_features` FeatureView |
| [feature_store/feature_pipeline.py](feature_store/feature_pipeline.py) | Computes 9 rolling-window features from Silver, writes to Parquet + Delta + Redis |
| [feature_store/offline_store.py](feature_store/offline_store.py) | Point-in-time correct training dataset builder via `store.get_historical_features()` |
| [verify_features.py](verify_features.py) | Verifies all 3 stores: offline Parquet, Redis, MinIO Delta |
| [tests/feature_store/test_feature_pipeline.py](tests/feature_store/test_feature_pipeline.py) | 19 unit tests — rolling window boundary conditions |

### The 9 features computed per user

| Feature | Window | What it captures |
|---------|--------|-----------------|
| `purchase_count_1h` | 1 hour | Burst buying behaviour |
| `purchase_count_24h` | 24 hours | Daily buying habit |
| `purchase_count_7d` | 7 days | Weekly purchase frequency |
| `revenue_sum_1h` | 1 hour | High-value session signal |
| `revenue_sum_24h` | 24 hours | Daily spend |
| `revenue_sum_7d` | 7 days | Weekly LTV signal |
| `session_count_24h` | 24 hours | Engagement depth |
| `event_count_24h` | 24 hours | Overall daily activity |
| `days_since_last_purchase` | — | Recency (999 = never purchased) |

### Why two stores?

| Store | Technology | Used for | Latency |
|-------|-----------|---------|---------|
| Online | Redis | Real-time inference (Phase 5 FastAPI) | < 10ms p99 |
| Offline | Parquet + Delta | Model training, point-in-time joins | seconds |

### Running Phase 4 locally

```bash
source .venv/bin/activate

# Run the feature pipeline (reads Silver → computes → writes to all 3 stores)
python -m feature_store.feature_pipeline

# Verify all stores
python verify_features.py

# Run unit tests
pytest tests/feature_store/ -v   # 19 tests, all pass
```

### Results

| Store | Records | Notes |
|-------|---------|-------|
| Offline Parquet | 3,940 users | 9 features per user |
| Redis online store | 3,940 users | Zero null values |
| MinIO Delta | 3,940 rows | Audit trail, time-travel |
| **Tests** | **105 / 105** | Across all 4 phases |

---

## Phase 5 — ML Loop

### What was built

| File | Purpose |
|------|---------|
| [ml/train.py](ml/train.py) | XGBoost churn model — trains, logs metrics + SHAP to MLflow, registers in model registry |
| [ml/shap_explainer.py](ml/shap_explainer.py) | SHAP `TreeExplainer` — global summary plot (MLflow artifact) + per-prediction top-3 features |
| [ml/ab_splitter.py](ml/ab_splitter.py) | Deterministic Champion/Challenger split via MD5 hash (90/10, no DB needed) |
| [serving/app.py](serving/app.py) | FastAPI inference API — `/predict`, `/features/{user_id}`, `/model/info`, `/health` |
| [verify_ml.py](verify_ml.py) | End-to-end verification: registry, predictions, SHAP, A/B split stats |
| [tests/ml/test_train.py](tests/ml/test_train.py) | Unit tests — training data shape, binary labels, null safety |
| [tests/ml/test_ab_splitter.py](tests/ml/test_ab_splitter.py) | Unit tests — determinism, 90/10 distribution across 5,000 users |

### API

Start:
```bash
uvicorn serving.app:app --reload --port 8000
```

**`POST /predict`** — churn score + SHAP explanation + A/B group:
```bash
curl -X POST http://localhost:8000/predict \
     -H 'Content-Type: application/json' \
     -d '{"user_id": "USER-006775"}'
```
```json
{
  "user_id": "USER-006775",
  "churn_probability": 0.0126,
  "churn_prediction": false,
  "model_version": "1",
  "ab_group": "champion",
  "top_features": [
    {"feature": "purchase_count_1h",  "shap_value": -3.3408, "direction": "decreases_churn"},
    {"feature": "purchase_count_24h", "shap_value": -0.9221, "direction": "decreases_churn"},
    {"feature": "purchase_count_7d",  "shap_value": -0.0304, "direction": "decreases_churn"}
  ],
  "features_used": { "purchase_count_1h": 1, "days_since_last_purchase": 0, "..." : "..." }
}
```

### Running Phase 5 locally

```bash
source .venv/bin/activate

# 1. Train model (logs to MLflow, registers in model registry)
python -m ml.train

# 2. Verify model, SHAP, A/B split (no server required)
python verify_ml.py

# 3. Start inference API
uvicorn serving.app:app --reload --port 8000

# 4. Run all tests
pytest tests/ -v   # 122 tests, all pass
```

### Results

| Check | Result |
|-------|--------|
| Model AUC | 1.0 (label derived from features — expected for demo) |
| Users scored | 3,940 |
| High-risk (≥0.70) | 3,825 (97.1% — users who never purchased) |
| Low-risk (<0.30) | 115 (2.9% — active purchasers) |
| A/B split | 90.3% champion / 9.7% challenger across 3,940 users |
| API latency | < 50ms (feature fetch from Redis + model inference + SHAP) |
| **Tests** | **122 / 122** across all 5 phases |

---

## Phase 6 — Observability

### What was built

| File | Purpose |
|------|---------|
| [serving/metrics.py](serving/metrics.py) | Prometheus metric definitions (predictions, latency, churn probability, PSI, drift alert) |
| [serving/drift_monitor.py](serving/drift_monitor.py) | PSI drift detector — compares current features vs training baseline |
| [serving/training_baseline.json](serving/training_baseline.json) | Training feature distribution snapshot (generated by `ml/train.py`) |
| [infra/grafana/dashboards/streamlake_ml.json](infra/grafana/dashboards/streamlake_ml.json) | Grafana dashboard: predictions/sec, latency p50/p95/p99, PSI bars, drift alert |
| [locust/locustfile.py](locust/locustfile.py) | Locust load test: 80% predict / 15% health / 5% features |
| [verify_observability.py](verify_observability.py) | Checks all 4 observability layers end-to-end |
| [tests/serving/test_drift_monitor.py](tests/serving/test_drift_monitor.py) | 11 PSI unit tests — identical/shifted/extreme distributions |

### PSI Drift Detection

Population Stability Index measures how much a feature distribution has shifted since training.

| PSI | Status | Action |
|-----|--------|--------|
| < 0.10 | 🟢 Stable | No action |
| 0.10 – 0.25 | 🟡 Moderate | Monitor closely |
| > 0.25 | 🔴 Significant | Trigger retraining |

```bash
python verify_observability.py   # shows PSI per feature
```

### Prometheus metrics exposed at `/metrics`

| Metric | Type | Description |
|--------|------|-------------|
| `streamlake_predictions_total` | Counter | Predictions by model_version, ab_group, prediction |
| `streamlake_prediction_latency_seconds` | Histogram | Feature fetch + inference + SHAP |
| `streamlake_churn_probability` | Histogram | Score distribution |
| `streamlake_feature_psi{feature}` | Gauge | PSI score per feature |
| `streamlake_drift_alert` | Gauge | 1 = retrain needed, 0 = stable |

### Grafana dashboard

Import `infra/grafana/dashboards/streamlake_ml.json` at [http://localhost:3000](http://localhost:3000).
Panels: predictions/sec, p50/p95/p99 latency, churn probability histogram, A/B pie, PSI bar gauge, drift alert stat.

### Load testing with Locust

```bash
# Headless — 50 users, 60s
locust -f locust/locustfile.py --headless -u 50 -r 5 -t 60s --host http://localhost:8000

# UI mode (open http://localhost:8089)
locust -f locust/locustfile.py --host http://localhost:8000
```

Target SLOs: p50 < 30ms, p99 < 100ms, error rate < 0.1%

### Results

| Check | Result |
|-------|--------|
| All features PSI | 0.00000 – 0.00026 (all stable 🟢) |
| Drift alert | OFF (no retraining needed) |
| Prometheus /metrics | ✓ 37 StreamLake metric series exported |
| Prometheus server | ✓ healthy at :9090 |
| Grafana | ✓ healthy at :3000 |
| Locustfile | ✓ ready |
| **Tests** | **133 / 133** across all 6 phases |

---

## License

MIT
