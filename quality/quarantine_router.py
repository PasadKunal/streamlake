"""
Routes invalid records to the Quarantine Delta table.

In Flink this is implemented via a side output stream:
    OutputTag<Row> quarantineTag = new OutputTag<Row>("quarantine"){};
    // In ProcessFunction: ctx.output(quarantineTag, invalidRow)

Here we collect quarantine records in a list and flush them to Delta.
"""
import json
from datetime import datetime, timezone

from storage.silver_schema import QUARANTINE_SCHEMA
from storage.delta_writer import write_batch


class QuarantineRouter:
    def __init__(self, table_path: str):
        self.table_path = table_path
        self._buffer: list[dict] = []
        self.total_routed = 0

    def route(self, record: dict, errors: list[str], reason: str = "validation_failure") -> None:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        quarantine_record = {
            "event_id": record.get("event_id"),
            "event_type": record.get("event_type"),
            "user_id": record.get("user_id"),
            "session_id": record.get("session_id"),
            "timestamp_ms": record.get("timestamp_ms"),
            "page_url": record.get("page_url"),
            "product_id": record.get("product_id"),
            "amount_cents": record.get("amount_cents"),
            "device_type": record.get("device_type"),
            "country_code": record.get("country_code"),
            "app_version": record.get("app_version"),
            "quarantine_reason": reason,
            "validation_errors": json.dumps(errors),
            "silver_processed_ms": now_ms,
            "ingestion_date": record.get("ingestion_date"),
        }
        self._buffer.append(quarantine_record)
        self.total_routed += 1

    def flush(self) -> int:
        if not self._buffer:
            return 0
        written = write_batch(self._buffer, self.table_path, QUARANTINE_SCHEMA)
        self._buffer.clear()
        return written
