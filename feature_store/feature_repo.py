"""
Feast feature repository — entity and feature view definitions.

Apply with:
    cd feature_store && feast apply
or programmatically via feature_pipeline.py (store.apply(...)).

Feature view: user_activity_features
Entity: user_id (string)
Offline source: feature_store/data/user_features.parquet (written by feature_pipeline.py)
Online store: Redis (materialized by feature_pipeline.py)
"""
from datetime import timedelta
from pathlib import Path

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Int64

REPO_DIR = Path(__file__).parent

user = Entity(
    name="user_id",
    description="Unique user identifier from event stream",
)

user_activity_source = FileSource(
    name="user_activity_source",
    path=str(REPO_DIR / "data" / "user_features.parquet"),
    timestamp_field="event_timestamp",
)

user_activity_features = FeatureView(
    name="user_activity_features",
    entities=[user],
    ttl=timedelta(days=7),
    schema=[
        Field(name="purchase_count_1h",        dtype=Int64),
        Field(name="purchase_count_24h",       dtype=Int64),
        Field(name="purchase_count_7d",        dtype=Int64),
        Field(name="revenue_sum_1h",           dtype=Int64),
        Field(name="revenue_sum_24h",          dtype=Int64),
        Field(name="revenue_sum_7d",           dtype=Int64),
        Field(name="session_count_24h",        dtype=Int64),
        Field(name="event_count_24h",          dtype=Int64),
        Field(name="days_since_last_purchase", dtype=Int64),
    ],
    source=user_activity_source,
    online=True,
)
