"""Tests for aws_collector.ml_utils — column swap detection"""
import pandas as pd

from aws_collector.ml_utils import _fix_column_swap


class TestFixColumnSwap:
    def test_correct_order_unchanged(self):
        df = pd.DataFrame({
            "instance_id": ["i-abc123", "i-def456"],
            "timestamp": ["2024-01-01T00:00:00+00:00", "2024-01-01T01:00:00+00:00"],
        })
        result = _fix_column_swap(df, "instance_id")
        assert result["instance_id"].iloc[0] == "i-abc123"
        assert "2024" in result["timestamp"].iloc[0]

    def test_swapped_columns_fixed(self):
        # Simulate the bug: instance_id has timestamps, timestamp has IDs
        df = pd.DataFrame({
            "instance_id": ["2024-01-01T00:00:00+00:00", "2024-01-01T01:00:00+00:00"],
            "timestamp": ["i-abc123", "i-def456"],
        })
        result = _fix_column_swap(df, "instance_id")
        assert result["instance_id"].iloc[0] == "i-abc123"
        assert "2024" in result["timestamp"].iloc[0]

    def test_missing_columns_no_error(self):
        df = pd.DataFrame({"foo": [1, 2]})
        result = _fix_column_swap(df, "instance_id")
        assert list(result.columns) == ["foo"]

    def test_rds_column_swap(self):
        df = pd.DataFrame({
            "db_instance_id": ["2024-06-01T12:00:00+00:00"],
            "timestamp": ["mydb-prod"],
        })
        result = _fix_column_swap(df, "db_instance_id")
        assert result["db_instance_id"].iloc[0] == "mydb-prod"

    def test_volume_id_swap(self):
        df = pd.DataFrame({
            "volume_id": ["2024-03-15T08:00:00+00:00"],
            "timestamp": ["vol-abc123def"],
        })
        result = _fix_column_swap(df, "volume_id")
        assert result["volume_id"].iloc[0] == "vol-abc123def"
