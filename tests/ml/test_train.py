"""Unit tests for the XGBoost training pipeline."""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path


PARQUET_EXISTS = Path("feature_store/data/user_features.parquet").exists()


@pytest.mark.skipif(not PARQUET_EXISTS, reason="Phase 4 parquet not generated yet")
class TestBuildTrainingData:
    def test_returns_dataframe_and_series(self):
        from ml.train import build_training_data, FEATURE_COLS
        X, y = build_training_data()
        assert isinstance(X, pd.DataFrame)
        assert isinstance(y, pd.Series)

    def test_feature_columns_match(self):
        from ml.train import build_training_data, FEATURE_COLS
        X, y = build_training_data()
        assert list(X.columns) == FEATURE_COLS

    def test_same_length(self):
        from ml.train import build_training_data
        X, y = build_training_data()
        assert len(X) == len(y)

    def test_label_is_binary(self):
        from ml.train import build_training_data
        _, y = build_training_data()
        assert set(y.unique()).issubset({0, 1})

    def test_no_nulls_in_features(self):
        from ml.train import build_training_data
        X, _ = build_training_data()
        assert X.isna().sum().sum() == 0

    def test_both_classes_present(self):
        from ml.train import build_training_data
        _, y = build_training_data()
        assert y.sum() > 0, "No positive (churn) labels"
        assert (y == 0).sum() > 0, "No negative (retained) labels"

    def test_churn_rate_is_reasonable(self):
        from ml.train import build_training_data
        _, y = build_training_data()
        rate = float(y.mean())
        assert 0.01 < rate < 0.99, f"Churn rate {rate:.2%} is unreasonable"
