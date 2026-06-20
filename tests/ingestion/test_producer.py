"""
Unit tests for the event producer (no Kafka connection required).
Tests event generation logic, schema compliance, and distribution.
"""
import json
import uuid
from pathlib import Path

import fastavro
import pytest

from ingestion.kafka_producer import (
    APP_VERSIONS,
    COUNTRY_CODES,
    DEVICE_TYPES,
    EVENT_TYPES,
    USERS,
    _generate_event,
)

SCHEMA_PATH = Path("ingestion/avro_schemas/user_event.avsc")


@pytest.fixture()
def avro_schema():
    raw = json.loads(SCHEMA_PATH.read_text())
    return fastavro.parse_schema(raw)


@pytest.fixture()
def active_sessions():
    return {}


class TestGenerateEvent:
    def test_returns_all_required_fields(self, active_sessions):
        event = _generate_event(active_sessions)
        required = {
            "event_id", "event_type", "user_id", "session_id",
            "timestamp_ms", "device_type", "country_code", "app_version",
        }
        assert required.issubset(event.keys())

    def test_event_id_is_valid_uuid(self, active_sessions):
        event = _generate_event(active_sessions)
        uuid.UUID(event["event_id"])  # raises ValueError if invalid

    def test_first_event_for_new_user_is_session_start(self):
        sessions = {}
        # Force a specific user with no existing session
        target_user = "USER-000001"
        original_choice = __builtins__  # noqa — just testing logic below

        # Clear sessions and generate until we see target user
        for _ in range(200):
            sessions = {}
            event = _generate_event(sessions)
            # Any new user should start with SESSION_START
            assert event["event_type"] == "SESSION_START"
            break

    def test_event_type_is_valid_enum_value(self, active_sessions):
        valid_types = set(EVENT_TYPES)
        for _ in range(50):
            event = _generate_event(active_sessions)
            assert event["event_type"] in valid_types

    def test_device_type_is_valid(self, active_sessions):
        valid_devices = set(DEVICE_TYPES)
        for _ in range(50):
            event = _generate_event(active_sessions)
            assert event["device_type"] in valid_devices

    def test_country_code_is_valid(self, active_sessions):
        valid_countries = set(COUNTRY_CODES)
        for _ in range(50):
            event = _generate_event(active_sessions)
            assert event["country_code"] in valid_countries

    def test_app_version_is_valid(self, active_sessions):
        valid_versions = set(APP_VERSIONS)
        for _ in range(50):
            event = _generate_event(active_sessions)
            assert event["app_version"] in valid_versions

    def test_purchase_event_has_amount(self, active_sessions):
        # Seed some sessions, then generate many events to get a PURCHASE
        for _ in range(500):
            event = _generate_event(active_sessions)
            if event["event_type"] == "PURCHASE":
                assert event["amount_cents"] is not None
                assert event["amount_cents"] > 0
                return
        pytest.skip("No PURCHASE event generated in 500 tries — increase sample size")

    def test_non_purchase_events_have_null_amount(self, active_sessions):
        found = False
        for _ in range(200):
            event = _generate_event(active_sessions)
            if event["event_type"] not in ("PURCHASE",):
                assert event["amount_cents"] is None
                found = True
                break
        assert found, "Expected at least one non-PURCHASE event in 200 tries"

    def test_timestamp_is_positive_ms(self, active_sessions):
        event = _generate_event(active_sessions)
        # 2020-01-01 in ms — sanity lower bound
        assert event["timestamp_ms"] > 1_577_836_800_000

    def test_late_events_have_past_timestamp(self, active_sessions):
        """At least some events should be behind wall-clock time (late events)."""
        import time

        now_ms = int(time.time() * 1000)
        late_found = False
        for _ in range(500):
            event = _generate_event(active_sessions)
            if event["timestamp_ms"] < now_ms - 30_000:  # more than 30s behind
                late_found = True
                break
        assert late_found, "Expected at least one late event in 500 tries (2% probability)"

    def test_session_accumulates_in_active_sessions(self):
        sessions = {}
        # First event always creates a session
        _generate_event(sessions)
        assert len(sessions) >= 1

    def test_avro_schema_validates_event(self, active_sessions, avro_schema):
        """Generated events must be valid against the Avro schema."""
        import io

        event = _generate_event(active_sessions)
        buf = io.BytesIO()
        fastavro.schemaless_writer(buf, avro_schema, event)
        assert buf.tell() > 0  # something was written
