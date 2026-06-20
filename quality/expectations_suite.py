"""
Great Expectations-style validation suite for the Silver layer.

Each method name mirrors a GE expectation so this maps directly to a
real GE ExpectationSuite if the team later upgrades to a managed GE setup.

Flink equivalent: a ProcessFunction that applies validations per record
and emits to main output (valid) or side output (quarantine).
"""
import re
from datetime import datetime, timezone

VALID_EVENT_TYPES = {"CLICK", "PAGE_VIEW", "PURCHASE", "SESSION_START", "SESSION_END", "ADD_TO_CART"}
VALID_DEVICE_TYPES = {"DESKTOP", "MOBILE", "TABLET", "UNKNOWN"}
COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")

# Timestamp sanity bounds: 2020-01-01 → 2035-01-01 in ms
TS_MIN_MS = 1_577_836_800_000
TS_MAX_MS = 2_051_222_400_000


class SilverValidator:
    """
    Validates a single Bronze record against the Silver data contract.
    Returns a list of expectation failure strings (empty = valid).

    GE mapping:
        expect_column_values_to_not_be_null         → null checks
        expect_column_values_to_be_in_set           → enum checks
        expect_column_values_to_match_regex          → country_code format
        expect_column_values_to_be_between          → timestamp range
        custom_conditional_expectation               → PURCHASE amount rule
    """

    def validate(self, record: dict) -> list[str]:
        errors: list[str] = []
        errors.extend(self._check_not_null(record))
        errors.extend(self._check_event_type(record))
        errors.extend(self._check_device_type(record))
        errors.extend(self._check_timestamp(record))
        errors.extend(self._check_country_code(record))
        errors.extend(self._check_purchase_amount(record))
        return errors

    def _check_not_null(self, r: dict) -> list[str]:
        required = ["event_id", "event_type", "user_id", "session_id",
                    "timestamp_ms", "device_type", "country_code", "app_version"]
        return [
            f"expect_column_values_to_not_be_null: '{col}'"
            for col in required
            if r.get(col) is None or r.get(col) == ""
        ]

    def _check_event_type(self, r: dict) -> list[str]:
        et = r.get("event_type")
        if et not in VALID_EVENT_TYPES:
            return [f"expect_column_values_to_be_in_set: event_type='{et}'"]
        return []

    def _check_device_type(self, r: dict) -> list[str]:
        dt = r.get("device_type")
        if dt not in VALID_DEVICE_TYPES:
            return [f"expect_column_values_to_be_in_set: device_type='{dt}'"]
        return []

    def _check_timestamp(self, r: dict) -> list[str]:
        ts = r.get("timestamp_ms")
        if ts is None:
            return []
        if not (TS_MIN_MS <= ts <= TS_MAX_MS):
            return [f"expect_column_values_to_be_between: timestamp_ms={ts}"]
        return []

    def _check_country_code(self, r: dict) -> list[str]:
        cc = r.get("country_code", "")
        if not COUNTRY_CODE_RE.match(str(cc)):
            return [f"expect_column_values_to_match_regex: country_code='{cc}'"]
        return []

    def _check_purchase_amount(self, r: dict) -> list[str]:
        if r.get("event_type") == "PURCHASE":
            amt = r.get("amount_cents")
            if amt is None or amt <= 0:
                return [f"conditional_expectation: PURCHASE requires amount_cents > 0, got {amt}"]
        return []


def validate_batch(records: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """
    Validate a batch of records. Returns (valid, invalid, stats).
    invalid records have a '_validation_errors' key injected.
    """
    validator = SilverValidator()
    valid, invalid = [], []
    for record in records:
        errors = validator.validate(record)
        if errors:
            record["_validation_errors"] = errors
            invalid.append(record)
        else:
            valid.append(record)

    stats = {
        "total": len(records),
        "valid": len(valid),
        "invalid": len(invalid),
        "pass_rate": len(valid) / len(records) if records else 1.0,
    }
    return valid, invalid, stats
