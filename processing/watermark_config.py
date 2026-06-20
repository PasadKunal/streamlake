"""
Watermark configuration for the Bronze → Silver pipeline.

In PyFlink this maps to WatermarkStrategy:
    WatermarkStrategy
        .for_bounded_out_of_orderness(Duration.ofMinutes(5))
        .with_idleness(Duration.ofSeconds(30))
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class WatermarkConfig:
    # Events arriving up to this far behind the watermark are still accepted
    allowed_lateness_ms: int = 5 * 60 * 1000   # 5 minutes

    # If no events arrive for this long, advance watermark anyway
    idle_timeout_ms: int = 30 * 1000            # 30 seconds

    # Late events beyond this threshold are discarded entirely (not quarantined)
    max_lateness_ms: int = 60 * 60 * 1000       # 1 hour


DEFAULT_WATERMARK_CONFIG = WatermarkConfig()
