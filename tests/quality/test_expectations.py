"""Unit tests for the Silver layer expectations suite."""
import pytest
from quality.expectations_suite import SilverValidator, validate_batch


@pytest.fixture()
def validator():
    return SilverValidator()


@pytest.fixture()
def valid_record():
    return {
        "event_id": "abc-123",
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


class TestSilverValidator:
    def test_valid_record_has_no_errors(self, validator, valid_record):
        assert validator.validate(valid_record) == []

    def test_missing_event_id_fails(self, validator, valid_record):
        valid_record["event_id"] = None
        errors = validator.validate(valid_record)
        assert any("event_id" in e for e in errors)

    def test_empty_user_id_fails(self, validator, valid_record):
        valid_record["user_id"] = ""
        errors = validator.validate(valid_record)
        assert any("user_id" in e for e in errors)

    def test_invalid_event_type_fails(self, validator, valid_record):
        valid_record["event_type"] = "UNKNOWN_TYPE"
        errors = validator.validate(valid_record)
        assert any("event_type" in e for e in errors)

    def test_invalid_device_type_fails(self, validator, valid_record):
        valid_record["device_type"] = "SMARTWATCH"
        errors = validator.validate(valid_record)
        assert any("device_type" in e for e in errors)

    def test_timestamp_too_old_fails(self, validator, valid_record):
        valid_record["timestamp_ms"] = 1_000_000_000  # year 2001
        errors = validator.validate(valid_record)
        assert any("timestamp_ms" in e for e in errors)

    def test_timestamp_in_future_fails(self, validator, valid_record):
        valid_record["timestamp_ms"] = 9_999_999_999_999
        errors = validator.validate(valid_record)
        assert any("timestamp_ms" in e for e in errors)

    def test_invalid_country_code_fails(self, validator, valid_record):
        valid_record["country_code"] = "usa"  # must be 2 uppercase letters
        errors = validator.validate(valid_record)
        assert any("country_code" in e for e in errors)

    def test_one_letter_country_code_fails(self, validator, valid_record):
        valid_record["country_code"] = "U"
        errors = validator.validate(valid_record)
        assert any("country_code" in e for e in errors)

    def test_purchase_without_amount_fails(self, validator, valid_record):
        valid_record["event_type"] = "PURCHASE"
        valid_record["amount_cents"] = None
        errors = validator.validate(valid_record)
        assert any("amount_cents" in e for e in errors)

    def test_purchase_with_zero_amount_fails(self, validator, valid_record):
        valid_record["event_type"] = "PURCHASE"
        valid_record["amount_cents"] = 0
        errors = validator.validate(valid_record)
        assert any("amount_cents" in e for e in errors)

    def test_purchase_with_valid_amount_passes(self, validator, valid_record):
        valid_record["event_type"] = "PURCHASE"
        valid_record["amount_cents"] = 9999
        assert validator.validate(valid_record) == []

    def test_non_purchase_with_null_amount_passes(self, validator, valid_record):
        valid_record["event_type"] = "CLICK"
        valid_record["amount_cents"] = None
        assert validator.validate(valid_record) == []

    def test_all_valid_event_types_pass(self, validator, valid_record):
        for et in ["CLICK", "PAGE_VIEW", "PURCHASE", "SESSION_START", "SESSION_END", "ADD_TO_CART"]:
            valid_record["event_type"] = et
            if et == "PURCHASE":
                valid_record["amount_cents"] = 1000
            else:
                valid_record["amount_cents"] = None
            assert validator.validate(valid_record) == [], f"Expected {et} to pass"


class TestValidateBatch:
    def test_empty_batch_returns_empty(self):
        valid, invalid, stats = validate_batch([])
        assert valid == []
        assert invalid == []
        assert stats["pass_rate"] == 1.0

    def test_all_valid_batch(self, valid_record):
        records = [dict(valid_record) for _ in range(10)]
        valid, invalid, stats = validate_batch(records)
        assert len(valid) == 10
        assert len(invalid) == 0
        assert stats["pass_rate"] == 1.0

    def test_mixed_batch_splits_correctly(self, valid_record):
        bad = dict(valid_record)
        bad["event_id"] = None
        records = [dict(valid_record), bad, dict(valid_record)]
        valid, invalid, stats = validate_batch(records)
        assert len(valid) == 2
        assert len(invalid) == 1
        assert stats["pass_rate"] == pytest.approx(2 / 3)

    def test_invalid_records_have_validation_errors_key(self, valid_record):
        bad = dict(valid_record)
        bad["event_type"] = "BOGUS"
        _, invalid, _ = validate_batch([bad])
        assert "_validation_errors" in invalid[0]
        assert isinstance(invalid[0]["_validation_errors"], list)
