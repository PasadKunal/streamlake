"""
Olist dataset producer - replays real Brazilian e-commerce orders as events.

Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
Place the 4 CSVs in data/olist/ before running:
    olist_orders_dataset.csv
    olist_customers_dataset.csv
    olist_order_payments_dataset.csv
    olist_order_items_dataset.csv

What this does:
    Reads ~99k real completed orders, maps each one to a PURCHASE event in
    our existing event schema, then time-compresses the full 2-year Olist
    history (Sep 2016 - Oct 2018) into the last --compress-days days so
    that the rolling-window features (1h, 24h, 7d) are meaningful.

Usage:
    python -m ingestion.olist_producer
    python -m ingestion.olist_producer --compress-days 30 --data-dir data/olist
    python -m ingestion.olist_producer --dry-run        # validate without sending
"""
from __future__ import annotations

import argparse
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer
from loguru import logger

from ingestion.schema_registry import USER_EVENT_SCHEMA_PATH

DATA_DIR = Path("data/olist")

REQUIRED_FILES = [
    "olist_orders_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_items_dataset.csv",
]


def load_olist(data_dir: Path) -> pd.DataFrame:
    """
    Load and join the 4 Olist tables, returning one row per delivered order.

    Columns in result:
        order_id, customer_unique_id, order_purchase_timestamp,
        total_payment_brl, first_product_id
    """
    for fname in REQUIRED_FILES:
        path = data_dir / fname
        if not path.exists():
            raise FileNotFoundError(
                f"Missing: {path}\n"
                f"Download from https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
            )

    logger.info("Loading Olist CSVs...")

    orders = pd.read_csv(data_dir / "olist_orders_dataset.csv")
    customers = pd.read_csv(data_dir / "olist_customers_dataset.csv")
    payments = pd.read_csv(data_dir / "olist_order_payments_dataset.csv")
    items = pd.read_csv(data_dir / "olist_order_items_dataset.csv")

    # Only delivered orders have a meaningful completion signal
    orders = orders[orders["order_status"] == "delivered"].copy()
    logger.info(f"Delivered orders: {len(orders):,}")

    # customer_unique_id persists across multiple customer_ids (loyalty identifier)
    orders = orders.merge(
        customers[["customer_id", "customer_unique_id"]],
        on="customer_id", how="left",
    )

    # Sum all payment rows per order (installments create multiple rows)
    total_payments = (
        payments.groupby("order_id")["payment_value"]
        .sum()
        .reset_index()
        .rename(columns={"payment_value": "total_payment_brl"})
    )
    orders = orders.merge(total_payments, on="order_id", how="left")

    # Take the first product per order (items are ordered by order_item_id)
    first_product = (
        items.sort_values("order_item_id")
        .groupby("order_id")["product_id"]
        .first()
        .reset_index()
        .rename(columns={"product_id": "first_product_id"})
    )
    orders = orders.merge(first_product, on="order_id", how="left")

    # Parse timestamps and drop rows with missing purchase time or amount
    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], utc=True, errors="coerce"
    )
    orders = orders.dropna(subset=["order_purchase_timestamp", "total_payment_brl"])
    orders = orders[orders["total_payment_brl"] > 0]

    logger.info(
        f"Orders after cleaning: {len(orders):,} "
        f"| unique customers: {orders['customer_unique_id'].nunique():,}"
    )
    return orders[
        ["order_id", "customer_unique_id", "order_purchase_timestamp",
         "total_payment_brl", "first_product_id"]
    ].sort_values("order_purchase_timestamp").reset_index(drop=True)


def compress_timestamps(
    df: pd.DataFrame,
    compress_days: int,
) -> pd.DataFrame:
    """
    Linearly map the full Olist time range onto [now - compress_days, now].

    Preserves relative ordering and inter-event spacing proportionally.
    The most recent Olist order maps to now; the oldest maps to now - compress_days.
    """
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - compress_days * 86_400_000

    orig_ms = df["order_purchase_timestamp"].astype("int64") // 1_000_000
    min_ts = orig_ms.min()
    max_ts = orig_ms.max()

    if min_ts == max_ts:
        df["timestamp_ms"] = now_ms
    else:
        df["timestamp_ms"] = (
            start_ms
            + (orig_ms - min_ts) / (max_ts - min_ts) * (now_ms - start_ms)
        ).astype("int64")

    logger.info(
        f"Timestamps compressed to last {compress_days} days "
        f"({datetime.fromtimestamp(start_ms/1000, tz=timezone.utc).date()} "
        f"to {datetime.fromtimestamp(now_ms/1000, tz=timezone.utc).date()})"
    )
    return df


def build_events(df: pd.DataFrame) -> list[dict]:
    """Convert each Olist order row to a PURCHASE event matching the Avro schema."""
    events = []
    for _, row in df.iterrows():
        events.append({
            "event_id":    str(uuid.uuid4()),
            "event_type":  "PURCHASE",
            "user_id":     str(row["customer_unique_id"]),
            "session_id":  str(row["order_id"]),
            "timestamp_ms": int(row["timestamp_ms"]),
            "page_url":    None,
            "product_id":  str(row["first_product_id"]) if pd.notna(row["first_product_id"]) else None,
            # BRL -> cents (1 BRL = 100 centavos, store as integer)
            "amount_cents": max(1, int(round(row["total_payment_brl"] * 100))),
            "device_type": "UNKNOWN",
            "country_code": "BR",
            "app_version":  "olist-1.0",
        })
    return events


def send_to_kafka(
    events: list[dict],
    bootstrap_servers: str,
    schema_registry_url: str,
    topic: str,
    batch_log_size: int = 5000,
) -> None:
    schema_str = USER_EVENT_SCHEMA_PATH.read_text()
    registry_client = SchemaRegistryClient({"url": schema_registry_url})
    avro_serializer = AvroSerializer(registry_client, schema_str, lambda obj, ctx: obj)

    producer = SerializingProducer({
        "bootstrap.servers": bootstrap_servers,
        "key.serializer":    StringSerializer("utf_8"),
        "value.serializer":  avro_serializer,
        "enable.idempotence": True,
        "acks":              "all",
        "linger.ms":         10,
        "batch.size":        131072,
    })

    sent = 0
    for event in events:
        producer.produce(
            topic=topic,
            key=event["user_id"],
            value=event,
        )
        producer.poll(0)
        sent += 1
        if sent % batch_log_size == 0:
            logger.info(f"Sent {sent:,} / {len(events):,} events")

    producer.flush(timeout=60)
    logger.info(f"Done - {sent:,} events sent to topic '{topic}'")


def run(
    data_dir: Path,
    compress_days: int,
    bootstrap_servers: str,
    schema_registry_url: str,
    topic: str,
    dry_run: bool,
) -> None:
    df = load_olist(data_dir)
    df = compress_timestamps(df, compress_days)
    events = build_events(df)

    logger.info(f"Built {len(events):,} PURCHASE events")

    if dry_run:
        sample = events[:3]
        logger.info("Dry run - sample events:")
        for e in sample:
            logger.info(e)
        logger.info("Pass --dry-run=false to send to Kafka")
        return

    send_to_kafka(events, bootstrap_servers, schema_registry_url, topic)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay Olist orders as Kafka events")
    parser.add_argument("--data-dir", default="data/olist",
                        help="Directory containing Olist CSVs (default: data/olist)")
    parser.add_argument("--compress-days", type=int, default=30,
                        help="Map Olist history onto last N days (default: 30)")
    parser.add_argument("--topic",
                        default=os.getenv("KAFKA_TOPIC_EVENTS", "streamlake.events.raw"))
    parser.add_argument("--bootstrap-servers",
                        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    parser.add_argument("--schema-registry",
                        default=os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081"))
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and print sample events without sending")
    args = parser.parse_args()

    run(
        data_dir=Path(args.data_dir),
        compress_days=args.compress_days,
        bootstrap_servers=args.bootstrap_servers,
        schema_registry_url=args.schema_registry,
        topic=args.topic,
        dry_run=args.dry_run,
    )
