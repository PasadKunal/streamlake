"""Unit tests for the watermark tracker and late event handler."""
import pytest
from processing.late_event_handler import WatermarkTracker
from processing.watermark_config import WatermarkConfig


@pytest.fixture()
def config():
    return WatermarkConfig(allowed_lateness_ms=300_000, max_lateness_ms=3_600_000)


@pytest.fixture()
def tracker(config):
    return WatermarkTracker(config=config)


class TestWatermarkTracker:
    def test_initial_watermark_is_zero(self, tracker):
        assert tracker.watermark_ms == 0

    def test_watermark_advances_with_max_timestamp(self, tracker):
        tracker.update(1_000_000)
        assert tracker.watermark_ms == 1_000_000 - 300_000

    def test_watermark_does_not_regress(self, tracker):
        tracker.update(1_000_000)
        tracker.update(500_000)   # older event — should not lower watermark
        assert tracker.watermark_ms == 1_000_000 - 300_000

    def test_on_time_event_within_window(self, tracker):
        tracker.update(1_000_000)
        # Event within the allowed lateness window
        assert tracker.classify(800_000) == "on_time"

    def test_event_at_exact_watermark_boundary_is_on_time(self, tracker):
        tracker.update(1_000_000)
        # watermark = 1_000_000 - 300_000 = 700_000
        assert tracker.classify(700_000) == "on_time"

    def test_event_below_watermark_is_late(self, tracker):
        tracker.update(1_000_000)
        # watermark = 700_000; event at 600_000 → late
        assert tracker.classify(600_000) == "late"

    def test_event_beyond_max_lateness_is_discarded(self, tracker):
        tracker.update(5_000_000)
        # max_lateness = 3_600_000; event at 0 → beyond max lateness
        assert tracker.classify(0) == "discard"

    def test_stats_returns_correct_fields(self, tracker):
        tracker.update(1_000_000)
        s = tracker.stats
        assert "max_event_ts_ms" in s
        assert "watermark_ms" in s
        assert s["max_event_ts_ms"] == 1_000_000

    def test_classify_on_time_for_new_events(self, tracker):
        base = 1_700_000_000_000
        tracker.update(base)
        assert tracker.classify(base + 1000) == "on_time"
        assert tracker.classify(base) == "on_time"
