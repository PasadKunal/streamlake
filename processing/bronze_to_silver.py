"""
Bronze → Silver micro-batch pipeline.

Reads new Bronze Delta records (incremental, tracked by Delta version),
applies the same logic a PyFlink job would apply, and writes to Silver.

Processing steps (mirrors flink_bronze_to_silver.py):
  1. Watermark classification  — on_time / late / discard
  2. Deduplication             — stateful LRU keyed on event_id
  3. Great Expectations        — 6 expectation types per record
  4. Quarantine routing        — failures → quarantine Delta table
  5. Silver write              — valid records → Silver Delta (partitioned by event_date)

Checkpoint: last processed Bronze Delta version stored in
.checkpoint/silver_checkpoint.json so each run only processes new data.

Usage:
    python -m processing.bronze_to_silver
    python -m processing.bronze_to_silver --batch-size 1000 --once
"""
import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
from deltalake import DeltaTable
from dotenv import load_dotenv
from loguru import logger

from processing.dedup import EventDeduplicator
from processing.late_event_handler import WatermarkTracker
from processing.watermark_config import DEFAULT_WATERMARK_CONFIG
from quality.expectations_suite import validate_batch
from quality.quarantine_router import QuarantineRouter
from storage.delta_writer import STORAGE_OPTIONS, write_batch
from storage.silver_schema import SILVER_SCHEMA

load_dotenv()

BRONZE_PATH = os.getenv("DELTA_BRONZE_PATH", "s3://streamlake-bronze/events")
SILVER_PATH = os.getenv("DELTA_SILVER_PATH", "s3://streamlake-silver/events")
QUARANTINE_PATH = os.getenv("DELTA_QUARANTINE_PATH", "s3://streamlake-silver/quarantine")
CHECKPOINT_FILE = Path(".checkpoint/silver_checkpoint.json")


def _load_checkpoint() -> int:
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text()).get("last_bronze_version", -1)
    return -1


def _save_checkpoint(version: int) -> None:
    CHECKPOINT_FILE.parent.mkdir(exist_ok=True)
    CHECKPOINT_FILE.write_text(json.dumps({"last_bronze_version": version, "updated_at": datetime.now(timezone.utc).isoformat()}))


def _nan_to_none(v):
    """Pandas reads nullable int columns as float NaN — convert back to None."""
    try:
        if v is not None and math.isnan(float(v)):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _to_silver_record(record: dict, classification: str, now_ms: int) -> dict:
    ts_ms = record["timestamp_ms"]
    event_date = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return {
        "event_id": record["event_id"],
        "event_type": record["event_type"],
        "user_id": record["user_id"],
        "session_id": record["session_id"],
        "timestamp_ms": int(ts_ms),
        "page_url": _nan_to_none(record.get("page_url")),
        "product_id": _nan_to_none(record.get("product_id")),
        "amount_cents": _nan_to_none(record.get("amount_cents")),
        "device_type": record["device_type"],
        "country_code": record["country_code"],
        "app_version": record["app_version"],
        "silver_processed_ms": now_ms,
        "watermark_classification": classification,
        "event_date": event_date,
    }


def run_once(batch_size: int = 2000) -> dict:
    last_version = _load_checkpoint()

    try:
        dt = DeltaTable(BRONZE_PATH, storage_options=STORAGE_OPTIONS)
    except Exception as e:
        logger.error(f"Cannot open Bronze table: {e}")
        return {}

    current_version = dt.version()
    if current_version <= last_version:
        logger.info(f"No new Bronze data (current version={current_version}, checkpoint={last_version})")
        return {"skipped": True}

    logger.info(f"Processing Bronze versions {last_version + 1} → {current_version}")
    df = dt.to_pandas()

    # Only process records added after the checkpoint (by ingestion order)
    # For a full re-run, last_version=-1 processes everything
    if last_version >= 0:
        # Use Delta time travel to read only new additions
        new_dt = dt.load_with_datetime(dt.history()[0]["timestamp"].isoformat()) if hasattr(dt.history()[0]["timestamp"], "isoformat") else dt
        df = new_dt.to_pandas()

    records = df.to_dict(orient="records")
    logger.info(f"Loaded {len(records):,} records from Bronze")

    watermark = WatermarkTracker(config=DEFAULT_WATERMARK_CONFIG)
    deduplicator = EventDeduplicator()
    quarantine = QuarantineRouter(QUARANTINE_PATH)

    silver_records: list[dict] = []
    late_records: list[dict] = []
    stats = {"total": 0, "on_time": 0, "late": 0, "discarded": 0, "duplicate": 0, "quarantined": 0, "silver": 0}

    for record in records:
        stats["total"] += 1
        ts_ms = record.get("timestamp_ms", 0)
        watermark.update(ts_ms)
        classification = watermark.classify(ts_ms)

        if classification == "discard":
            stats["discarded"] += 1
            continue

        if deduplicator.is_duplicate(record.get("event_id", ""), ts_ms):
            stats["duplicate"] += 1
            continue

        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        silver_candidate = _to_silver_record(record, classification, now_ms)

        if classification == "late":
            stats["late"] += 1
            late_records.append(silver_candidate)
        else:
            stats["on_time"] += 1
            silver_records.append(silver_candidate)

        if len(silver_records) >= batch_size:
            valid, invalid, batch_stats = validate_batch(silver_records)
            write_batch(valid, SILVER_PATH, SILVER_SCHEMA, ["event_date"])
            for inv in invalid:
                quarantine.route(inv, inv.pop("_validation_errors", []))
            stats["silver"] += len(valid)
            stats["quarantined"] += len(invalid)
            silver_records.clear()
            logger.info(f"Flushed batch | silver={len(valid)} quarantine={len(invalid)} pass_rate={batch_stats['pass_rate']:.1%}")

    # Final flush
    if silver_records:
        valid, invalid, batch_stats = validate_batch(silver_records)
        write_batch(valid, SILVER_PATH, SILVER_SCHEMA, ["event_date"])
        for inv in invalid:
            quarantine.route(inv, inv.pop("_validation_errors", []))
        stats["silver"] += len(valid)
        stats["quarantined"] += len(invalid)

    if late_records:
        write_batch(late_records, SILVER_PATH, SILVER_SCHEMA, ["event_date"])
        stats["silver"] += len(late_records)

    quarantine.flush()
    _save_checkpoint(current_version)

    dedup_stats = deduplicator.stats
    wm_stats = watermark.stats
    logger.info(
        f"Pipeline complete | "
        f"total={stats['total']:,} silver={stats['silver']:,} "
        f"quarantine={stats['quarantined']} late={stats['late']} "
        f"duplicates={stats['duplicate']} discarded={stats['discarded']} | "
        f"watermark={datetime.fromtimestamp(wm_stats['watermark_ms']/1000, tz=timezone.utc).isoformat()} | "
        f"dedup_state_size={dedup_stats['state_size']:,}"
    )
    return stats


def run_continuous(batch_size: int, poll_interval_s: float = 15.0) -> None:
    logger.info(f"Continuous mode — polling Bronze every {poll_interval_s}s")
    while True:
        try:
            run_once(batch_size)
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
        time.sleep(poll_interval_s)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bronze → Silver micro-batch pipeline")
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--once", action="store_true", help="Run once and exit (default: continuous)")
    parser.add_argument("--poll-interval", type=float, default=15.0)
    args = parser.parse_args()

    if args.once:
        run_once(args.batch_size)
    else:
        run_continuous(args.batch_size, args.poll_interval)
