"""Unit tests for PSI drift detection."""
import numpy as np
import pytest
from serving.drift_monitor import compute_psi, psi_status, PSI_STABLE, PSI_RETRAIN


class TestComputePsi:
    def _baseline(self, values: list[float], bins: int = 10):
        """Helper: build baseline histogram from values."""
        counts, edges = np.histogram(values, bins=bins)
        return counts.tolist(), edges.tolist()

    def test_identical_distributions_give_near_zero_psi(self):
        values = list(range(1000))
        counts, edges = self._baseline(values)
        psi = compute_psi(counts, edges, np.array(values, dtype=float))
        assert psi < 0.01

    def test_shifted_distribution_gives_nonzero_psi(self):
        baseline_vals = list(range(0, 100))
        counts, edges = self._baseline(baseline_vals)
        # Shift actual distribution by +50
        actual = np.array(list(range(50, 150)), dtype=float)
        psi = compute_psi(counts, edges, actual)
        assert psi > PSI_STABLE

    def test_completely_different_distribution_gives_high_psi(self):
        baseline_vals = [0] * 500 + [1] * 500
        counts, edges = self._baseline(baseline_vals)
        # All values at the high end
        actual = np.full(1000, 999.0)
        psi = compute_psi(counts, edges, actual)
        assert psi > PSI_RETRAIN

    def test_psi_is_non_negative(self):
        rng = np.random.default_rng(42)
        baseline = rng.normal(0, 1, 1000).tolist()
        counts, edges = self._baseline(baseline)
        actual = rng.normal(0.5, 1.2, 1000)
        psi = compute_psi(counts, edges, actual)
        assert psi >= 0.0

    def test_returns_float(self):
        counts, edges = self._baseline(list(range(100)))
        result = compute_psi(counts, edges, np.arange(100, dtype=float))
        assert isinstance(result, float)

    def test_handles_zeros_in_actual_without_error(self):
        counts, edges = self._baseline(list(range(100)))
        # Actual is empty in some bins — should not raise ZeroDivisionError
        actual = np.zeros(100)
        psi = compute_psi(counts, edges, actual)
        assert psi >= 0.0


class TestPsiStatus:
    def test_below_stable_threshold(self):
        assert psi_status(0.0) == "stable"
        assert psi_status(0.09) == "stable"

    def test_at_stable_threshold(self):
        assert psi_status(PSI_STABLE) == "moderate"

    def test_moderate_range(self):
        assert psi_status(0.15) == "moderate"
        assert psi_status(0.24) == "moderate"

    def test_at_retrain_threshold(self):
        assert psi_status(PSI_RETRAIN) == "retrain"

    def test_above_retrain_threshold(self):
        assert psi_status(0.5) == "retrain"
        assert psi_status(1.0) == "retrain"
