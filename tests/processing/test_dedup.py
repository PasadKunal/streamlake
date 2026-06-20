"""Unit tests for the stateful event deduplicator."""
import time
import pytest
from processing.dedup import EventDeduplicator


class TestEventDeduplicator:
    def test_first_occurrence_is_not_duplicate(self):
        d = EventDeduplicator()
        assert d.is_duplicate("evt-001", 1_700_000_000_000) is False

    def test_second_occurrence_is_duplicate(self):
        d = EventDeduplicator()
        d.is_duplicate("evt-001", 1_700_000_000_000)
        assert d.is_duplicate("evt-001", 1_700_000_000_000) is True

    def test_different_ids_are_not_duplicates(self):
        d = EventDeduplicator()
        assert d.is_duplicate("evt-001", 1_700_000_000_000) is False
        assert d.is_duplicate("evt-002", 1_700_000_000_001) is False

    def test_stats_total_seen_increments(self):
        d = EventDeduplicator()
        d.is_duplicate("a", 1000)
        d.is_duplicate("b", 2000)
        assert d.stats["total_seen"] == 2
        assert d.stats["total_duplicates"] == 0

    def test_stats_duplicate_count(self):
        d = EventDeduplicator()
        d.is_duplicate("a", 1000)
        d.is_duplicate("a", 1000)  # duplicate
        assert d.stats["total_duplicates"] == 1
        assert d.stats["duplicate_rate"] == pytest.approx(0.5)

    def test_lru_eviction_when_over_max_size(self):
        d = EventDeduplicator(max_size=5)
        for i in range(10):
            d.is_duplicate(f"evt-{i}", i * 1000)
        # State should not grow beyond max_size
        assert d.stats["state_size"] <= 5

    def test_ttl_eviction_removes_expired_entries(self):
        d = EventDeduplicator(ttl_ms=1000)  # 1 second TTL
        d.is_duplicate("evt-old", 1000)
        assert d.stats["state_size"] == 1
        # Simulate time passing beyond TTL
        future_ms = int(time.time() * 1000) + 2000
        evicted = d.evict_expired(current_ms=future_ms)
        assert evicted == 1
        assert d.stats["state_size"] == 0

    def test_after_ttl_eviction_same_id_is_accepted_again(self):
        d = EventDeduplicator(ttl_ms=1000)
        d.is_duplicate("evt-001", 1000)
        future_ms = int(time.time() * 1000) + 2000
        d.evict_expired(current_ms=future_ms)
        # Should no longer be seen as duplicate
        assert d.is_duplicate("evt-001", future_ms) is False
