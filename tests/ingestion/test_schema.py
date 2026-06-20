"""
Tests for the Avro schema and Schema Registry utilities.
No network connections — purely validates schema structure and loading.
"""
import json
from pathlib import Path

import fastavro
import pytest

SCHEMA_PATH = Path("ingestion/avro_schemas/user_event.avsc")

REQUIRED_FIELDS = {
    "event_id",
    "event_type",
    "user_id",
    "session_id",
    "timestamp_ms",
    "device_type",
    "country_code",
    "app_version",
}

NULLABLE_FIELDS = {"page_url", "product_id", "amount_cents"}


class TestAvroSchema:
    def test_schema_file_exists(self):
        assert SCHEMA_PATH.exists(), f"Schema file not found: {SCHEMA_PATH}"

    def test_schema_is_valid_json(self):
        raw = SCHEMA_PATH.read_text()
        schema = json.loads(raw)
        assert schema["type"] == "record"
        assert schema["name"] == "UserEvent"
        assert schema["namespace"] == "com.streamlake.events"

    def test_schema_parses_with_fastavro(self):
        raw = json.loads(SCHEMA_PATH.read_text())
        parsed = fastavro.parse_schema(raw)
        assert parsed is not None

    def test_required_fields_present(self):
        raw = json.loads(SCHEMA_PATH.read_text())
        field_names = {f["name"] for f in raw["fields"]}
        missing = REQUIRED_FIELDS - field_names
        assert not missing, f"Missing required fields: {missing}"

    def test_nullable_fields_have_null_union(self):
        raw = json.loads(SCHEMA_PATH.read_text())
        field_map = {f["name"]: f for f in raw["fields"]}
        for fname in NULLABLE_FIELDS:
            assert fname in field_map, f"Expected nullable field '{fname}' in schema"
            ftype = field_map[fname]["type"]
            assert isinstance(ftype, list) and "null" in ftype, (
                f"Field '{fname}' should be a nullable union (got {ftype})"
            )

    def test_event_type_enum_has_expected_symbols(self):
        raw = json.loads(SCHEMA_PATH.read_text())
        field_map = {f["name"]: f for f in raw["fields"]}
        event_type_field = field_map["event_type"]
        symbols = event_type_field["type"]["symbols"]
        expected = {"CLICK", "PAGE_VIEW", "PURCHASE", "SESSION_START", "SESSION_END", "ADD_TO_CART"}
        assert expected == set(symbols), f"EventType symbols mismatch: {symbols}"

    def test_device_type_enum_has_expected_symbols(self):
        raw = json.loads(SCHEMA_PATH.read_text())
        field_map = {f["name"]: f for f in raw["fields"]}
        device_type_field = field_map["device_type"]
        symbols = device_type_field["type"]["symbols"]
        expected = {"DESKTOP", "MOBILE", "TABLET", "UNKNOWN"}
        assert expected == set(symbols)

    def test_timestamp_field_is_long(self):
        raw = json.loads(SCHEMA_PATH.read_text())
        field_map = {f["name"]: f for f in raw["fields"]}
        assert field_map["timestamp_ms"]["type"] == "long"

    def test_amount_cents_is_nullable_long(self):
        raw = json.loads(SCHEMA_PATH.read_text())
        field_map = {f["name"]: f for f in raw["fields"]}
        ftype = field_map["amount_cents"]["type"]
        assert isinstance(ftype, list)
        assert "null" in ftype
        assert "long" in ftype

    def test_schema_roundtrip_with_valid_record(self):
        """A valid record serializes and deserializes without error."""
        import io

        raw = json.loads(SCHEMA_PATH.read_text())
        schema = fastavro.parse_schema(raw)

        record = {
            "event_id": "abc123",
            "event_type": "CLICK",
            "user_id": "USER-000001",
            "session_id": "sess-xyz",
            "timestamp_ms": 1_700_000_000_000,
            "page_url": "/products",
            "product_id": "PROD-0001",
            "amount_cents": None,
            "device_type": "MOBILE",
            "country_code": "US",
            "app_version": "2.3.1",
        }

        buf = io.BytesIO()
        fastavro.schemaless_writer(buf, schema, record)
        buf.seek(0)
        decoded = fastavro.schemaless_reader(buf, schema)

        assert decoded["event_id"] == record["event_id"]
        assert decoded["event_type"] == record["event_type"]
        assert decoded["amount_cents"] is None
