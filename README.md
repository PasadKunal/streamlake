# StreamLake

A real-time data lakehouse built end-to-end: Kafka event ingestion, Delta Lake medallion storage on AWS S3, Redis feature store, XGBoost churn model with SHAP explanations, and a live FastAPI inference API.

**Live demo:** [streamlake.streamlit.app](https://streamlake.streamlit.app)
**API:** [streamlake.onrender.com](https://streamlake.onrender.com/docs)

---

## What it does

Order events flow from Kafka through three Delta Lake layers on S3, get aggregated into per-user rolling-window features, and power a real-time churn prediction API. Every prediction comes with a SHAP explanation and is automatically A/B tested across champion and challenger model versions.

```
Kafka / REST / CSV
       |
  Bronze Layer (S3)       raw, immutable events
       |
  Silver Layer (S3)       validated, deduplicated, watermarked
       |
  Feature Pipeline        9 rolling-window features per user
       |
  Redis (online)          sub-10ms feature retrieval at inference
       |
  FastAPI + XGBoost       churn probability + SHAP + A/B split
       |
  Drift Monitor           PSI computed daily vs training baseline
```

---

## Live numbers

| Metric | Value |
|--------|-------|
| Bronze events | 96,486 |
| Silver events | 96,477 (0 late, 0 quarantined) |
| Feature store users | 93,357 unique users in Redis |
| Model AUC | 0.851 (XGBoost v6) |
| Drift status | All 9 features stable (PSI below 0.02) |
| Training baseline | 74,685 samples |
| Current production | 93,357 samples |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Event streaming | Kafka (Redpanda Cloud) + Confluent Schema Registry (Avro) |
| Storage | Delta Lake on AWS S3 (delta-rs / deltalake Python) |
| Batch orchestration | Apache Airflow 2.9 |
| Data quality | Great Expectations (6 validation rules per record) |
| Feature store | Feast 0.39 + Redis Cloud (online) + Delta (offline) |
| ML training | XGBoost + MLflow (tracking + model registry) |
| Explainability | SHAP TreeExplainer (per-prediction top-3 features) |
| A/B testing | Deterministic MD5 hash split, 90/10 champion/challenger |
| Drift detection | PSI (Population Stability Index) across all 9 features |
| Inference API | FastAPI + Uvicorn, deployed on Render |
| Monitoring | Prometheus metrics + Grafana dashboard |
| Demo UI | Streamlit, deployed on Streamlit Cloud |
| Auth | Multi-tenant API keys (X-Api-Key header, tenant-namespaced S3 + Redis) |

---

## Architecture phases

**Phase 1: Event ingestion**
Kafka producer simulates purchase events at 1,400 events/sec. A consumer reads from Kafka and writes to Delta Lake on S3 with manual offset commit after each successful write. Schema is registered in Confluent Schema Registry using Avro.

**Phase 2: Bronze to Silver**
Micro-batch pipeline applies event-time watermarks (5-minute allowed lateness), deduplication keyed on event_id with 1-hour TTL, and 6 Great Expectations validation rules per record. Failed records route to a quarantine Delta table. Checkpoint-based so reruns are incremental.

**Phase 3: Silver to Gold**
Airflow DAG runs nightly to compute DAU, revenue by cohort, funnel conversion rates, and per-user churn signals. Written to Gold Delta tables Z-ordered for query patterns.

**Phase 4: Feature store**
Rolling-window aggregates (1h, 24h, 7d) computed per user from Silver events. Written atomically to Redis for online serving and Delta for offline training. Feast manages entity definitions, feature views, and point-in-time correct training dataset generation.

**Phase 5: ML loop**
XGBoost trained on Feast offline features, tracked in MLflow, registered in MLflow Model Registry. FastAPI loads champion and challenger models at startup. Each `/predict` request gets A/B assigned via MD5 hash, runs SHAP, and writes the score to Redis for the `/alerts` endpoint.

**Phase 6: Observability**
PSI computed daily for all 9 features against the training baseline stored in `serving/training_baseline.json`. Prometheus metrics exposed at `/metrics`. Grafana dashboard covers predictions/sec, latency p50/p95/p99, PSI bar chart, and drift alert.

---

## The 9 features

| Feature | Window | What it captures |
|---------|--------|-----------------|
| `purchase_count_1h` | 1 hour | Burst buying |
| `purchase_count_24h` | 24 hours | Daily habit |
| `purchase_count_7d` | 7 days | Weekly frequency |
| `revenue_sum_1h` | 1 hour | High-value session |
| `revenue_sum_24h` | 24 hours | Daily spend |
| `revenue_sum_7d` | 7 days | Weekly LTV |
| `session_count_24h` | 24 hours | Engagement depth |
| `event_count_24h` | 24 hours | Overall activity |
| `days_since_last_purchase` | all time | Recency (999 if never purchased) |

---

## API

The inference API is live at `https://streamlake.onrender.com`. First request may take 30 seconds to wake the free-tier instance.

**Predict churn:**
```bash
curl -X POST https://streamlake.onrender.com/predict \
     -H 'Content-Type: application/json' \
     -H 'X-Api-Key: sk-demo-streamlake' \
     -d '{"user_id": "063342fa545494715cc59f983598c546"}'
```

**Ingest an event via webhook:**
```bash
curl -X POST https://streamlake.onrender.com/ingest/webhook \
     -H 'Content-Type: application/json' \
     -H 'X-Api-Key: sk-demo-streamlake' \
     -d '{"user_id": "USER-001", "event_type": "PURCHASE", "amount_cents": 4999}'
```

**Get at-risk users:**
```bash
curl "https://streamlake.onrender.com/alerts?threshold=0.7" \
     -H 'X-Api-Key: sk-demo-streamlake'
```

**Health check:**
```bash
curl https://streamlake.onrender.com/health
```

---

## Running locally

**Prerequisites:** Docker, Python 3.11, Java 11+ (for PyFlink only)

```bash
git clone https://github.com/PasadKunal/streamlake.git
cd streamlake
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your AWS and Redis credentials
docker compose up -d   # starts MinIO, Redis, PostgreSQL, Grafana, Prometheus
```

Run the full pipeline:
```bash
python -m ingestion.kafka_producer --rate 1400   # terminal 1
python -m ingestion.kafka_to_bronze               # terminal 2
python -m processing.bronze_to_silver --once
python -m feature_store.feature_pipeline
python -m ml.train
uvicorn serving.app:app --reload --port 8000
```

Run all tests:
```bash
pytest tests/ -v   # 133 tests across all 6 phases
```

Run the Streamlit demo locally:
```bash
streamlit run demo.py
```

---

## Repository structure

```
streamlake/
├── ingestion/            # Kafka producer, Avro schemas, Bronze Delta writer
├── processing/           # Bronze-to-Silver pipeline, watermark, dedup
├── storage/              # Delta writers, schema definitions
├── quality/              # Great Expectations suites, quarantine router
├── feature_store/        # Feast definitions, feature pipeline, online/offline stores
├── ml/                   # Model training, MLflow, A/B splitter, SHAP
├── serving/              # FastAPI API, drift monitor, Prometheus metrics, auth
├── orchestration/
│   └── dags/             # Airflow DAGs (Gold refresh, quality checks, retraining)
├── infra/
│   ├── grafana/          # Grafana dashboard JSON
│   └── prometheus/       # Prometheus scrape config
├── locust/               # Load test (80% predict, 15% health, 5% features)
├── demo.py               # Streamlit demo UI
├── docker-compose.yml    # Local stack (Redpanda, MinIO, Redis, PostgreSQL, Grafana)
└── render.yaml           # Render deployment config
```

---

## License

MIT
