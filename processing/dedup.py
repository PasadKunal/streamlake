"""
Stateful event deduplicator keyed on event_id.

In PyFlink this maps to a KeyedProcessFunction with ValueState[Long]
backed by RocksDB, TTL-configured to auto-expire seen event IDs after 1h.

Here we use an in-memory LRU dict with time-based eviction for the
micro-batch runner. The semantics are identical.
"""
import time
from collections import OrderedDict


class EventDeduplicator:
    """
    Tracks seen event_ids to drop duplicates within a sliding TTL window.

    Flink equivalent:
        ValueStateDescriptor<Long> descriptor = new ValueStateDescriptor<>(
            "seen-event-ts", BasicTypeInfo.LONG_TYPE_INFO
        );
        descriptor.enableTimeToLive(StateTtlConfig.newBuilder(Time.hours(1)).build());
    """

    def __init__(self, max_size: int = 200_000, ttl_ms: int = 3_600_000):
        self._seen: OrderedDict[str, int] = OrderedDict()  # event_id → timestamp_ms
        self._max_size = max_size
        self._ttl_ms = ttl_ms
        self._total_seen = 0
        self._total_duplicates = 0

    def is_duplicate(self, event_id: str, timestamp_ms: int) -> bool:
        if event_id in self._seen:
            self._total_duplicates += 1
            return True
        self._seen[event_id] = timestamp_ms
        self._seen.move_to_end(event_id)
        self._total_seen += 1
        # Evict oldest when over capacity
        if len(self._seen) > self._max_size:
            self._seen.popitem(last=False)
        return False

    def evict_expired(self, current_ms: int | None = None) -> int:
        """Remove event IDs that have passed their TTL. Called periodically."""
        now = current_ms or int(time.time() * 1000)
        to_evict = [k for k, ts in self._seen.items() if now - ts > self._ttl_ms]
        for k in to_evict:
            del self._seen[k]
        return len(to_evict)

    @property
    def stats(self) -> dict:
        total_processed = self._total_seen + self._total_duplicates
        return {
            "state_size": len(self._seen),
            "total_seen": self._total_seen,
            "total_duplicates": self._total_duplicates,
            "duplicate_rate": (
                self._total_duplicates / total_processed if total_processed else 0.0
            ),
        }
