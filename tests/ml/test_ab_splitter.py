"""Unit tests for the A/B splitter."""
import pytest
from ml.ab_splitter import assign, split_stats


class TestAssign:
    def test_returns_champion_or_challenger(self):
        result = assign("USER-000001")
        assert result in ("champion", "challenger")

    def test_deterministic_same_user(self):
        uid = "USER-042"
        assert assign(uid) == assign(uid)

    def test_deterministic_across_calls(self):
        uids = [f"USER-{i:06d}" for i in range(100)]
        first  = [assign(u) for u in uids]
        second = [assign(u) for u in uids]
        assert first == second

    def test_different_users_can_get_different_groups(self):
        results = {assign(f"USER-{i:06d}") for i in range(200)}
        assert "champion" in results
        assert "challenger" in results

    def test_custom_champion_pct_100(self):
        for i in range(50):
            assert assign(f"USER-{i}", champion_pct=1.0) == "champion"

    def test_custom_champion_pct_0(self):
        for i in range(50):
            assert assign(f"USER-{i}", champion_pct=0.0) == "challenger"


class TestSplitStats:
    def test_returns_correct_keys(self):
        stats = split_stats(["USER-001", "USER-002"])
        assert "total" in stats
        assert "champion" in stats
        assert "challenger" in stats
        assert "champion_pct" in stats

    def test_total_matches_input(self):
        uids = [f"USER-{i}" for i in range(50)]
        stats = split_stats(uids)
        assert stats["total"] == 50
        assert stats["champion"] + stats["challenger"] == 50

    def test_large_sample_approximates_90_10(self):
        uids = [f"USER-{i:06d}" for i in range(5000)]
        stats = split_stats(uids)
        # Allow ±5% tolerance from expected 90%
        assert 0.85 <= stats["champion_pct"] <= 0.95, \
            f"Champion pct {stats['champion_pct']:.2%} outside 85-95% band"

    def test_empty_list(self):
        stats = split_stats([])
        assert stats["total"] == 0
        assert stats["champion_pct"] == 0.0
