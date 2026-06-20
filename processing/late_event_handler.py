"""
Watermark tracker and late event handler for event-time processing.

In PyFlink this is implemented via BoundedOutOfOrdernessWatermarks inside
WatermarkStrategy.for_bounded_out_of_orderness(). Here we replicate the
same semantics in plain Python for the micro-batch runner.
"""
import time
from dataclasses import dataclass, field

from processing.watermark_config import WatermarkConfig, DEFAULT_WATERMARK_CONFIG


@dataclass
class WatermarkTracker:
    """
    Tracks the current watermark as: max_observed_event_ts - allowed_lateness.
    Events whose timestamp falls below the watermark are considered late.
    """
    config: WatermarkConfig = field(default_factory=lambda: DEFAULT_WATERMARK_CONFIG)
    _max_event_ts_ms: int = field(default=0, init=False)
    _last_event_wall_ms: int = field(default_factory=lambda: int(time.time() * 1000), init=False)

    def update(self, timestamp_ms: int) -> None:
        if timestamp_ms > self._max_event_ts_ms:
            self._max_event_ts_ms = timestamp_ms
        self._last_event_wall_ms = int(time.time() * 1000)

    @property
    def watermark_ms(self) -> int:
        return max(0, self._max_event_ts_ms - self.config.allowed_lateness_ms)

    def classify(self, timestamp_ms: int) -> str:
        """
        Returns:
          'on_time'   — within the watermark window, process normally
          'late'      — past watermark but within max_lateness, route to late_events table
          'discard'   — too old, drop silently
        """
        if timestamp_ms >= self.watermark_ms:
            return "on_time"
        if timestamp_ms >= self._max_event_ts_ms - self.config.max_lateness_ms:
            return "late"
        return "discard"

    @property
    def stats(self) -> dict:
        return {
            "max_event_ts_ms": self._max_event_ts_ms,
            "watermark_ms": self.watermark_ms,
            "allowed_lateness_ms": self.config.allowed_lateness_ms,
        }
