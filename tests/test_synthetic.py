"""Tests for data_generation.synthetic"""
import pandas as pd
import numpy as np

from data_generation.synthetic import (
    generate_daily_costs,
    generate_service_costs,
    generate_ec2_instances,
    generate_ec2_metrics,
    generate_rds_instances,
    generate_rds_metrics,
    generate_s3_buckets,
    generate_lambda_functions,
    generate_ebs_volumes,
    generate_instance_pricing,
)


class TestDailyCosts:
    def test_row_count(self):
        df = generate_daily_costs(days=30, seed=1)
        assert len(df) == 30

    def test_columns(self):
        df = generate_daily_costs(days=30, seed=1)
        assert "date" in df.columns
        assert "cost_amount" in df.columns

    def test_no_negative_costs(self):
        df = generate_daily_costs(days=180, seed=42)
        assert (df["cost_amount"] >= 0).all()

    def test_reproducible(self):
        df1 = generate_daily_costs(days=30, seed=99)
        df2 = generate_daily_costs(days=30, seed=99)
        pd.testing.assert_frame_equal(df1, df2)


class TestServiceCosts:
    def test_has_service_column(self):
        df = generate_service_costs(days=30, seed=1)
        assert "service_name" in df.columns

    def test_multiple_services(self):
        df = generate_service_costs(days=30, seed=1)
        assert df["service_name"].nunique() >= 5

    def test_no_negative_costs(self):
        df = generate_service_costs(days=30, seed=1)
        assert (df["cost_amount"] >= 0).all()


class TestEC2Instances:
    def test_fleet_size(self):
        df = generate_ec2_instances()
        assert len(df) == 8  # EC2_FLEET has 8 instances

    def test_required_columns(self):
        df = generate_ec2_instances()
        for col in ["instance_id", "instance_type", "state", "region"]:
            assert col in df.columns

    def test_instance_ids_unique(self):
        df = generate_ec2_instances()
        assert df["instance_id"].is_unique


class TestEC2Metrics:
    def test_cpu_range(self):
        df = generate_ec2_metrics(days=7, seed=1)
        assert (df["cpu_avg"] >= 0).all()
        assert (df["cpu_avg"] <= 100).all()

    def test_has_timestamp(self):
        df = generate_ec2_metrics(days=7, seed=1)
        assert "timestamp" in df.columns

    def test_has_instance_id(self):
        df = generate_ec2_metrics(days=7, seed=1)
        assert "instance_id" in df.columns

    def test_multiple_instances(self):
        df = generate_ec2_metrics(days=7, seed=1)
        assert df["instance_id"].nunique() == 8


class TestRDSInstances:
    def test_count(self):
        df = generate_rds_instances()
        assert len(df) >= 1

    def test_required_columns(self):
        df = generate_rds_instances()
        for col in ["db_instance_id", "db_instance_class", "engine"]:
            assert col in df.columns


class TestRDSMetrics:
    def test_cpu_range(self):
        df = generate_rds_metrics(days=7, seed=1)
        cpu_cols = [c for c in df.columns if "cpu" in c.lower()]
        for col in cpu_cols:
            assert (df[col] >= 0).all()
            assert (df[col] <= 100).all()


class TestS3Buckets:
    def test_count(self):
        df = generate_s3_buckets()
        assert len(df) >= 1

    def test_bucket_names_unique(self):
        df = generate_s3_buckets()
        assert df["bucket_name"].is_unique


class TestLambdaFunctions:
    def test_count(self):
        df = generate_lambda_functions()
        assert len(df) >= 1

    def test_required_columns(self):
        df = generate_lambda_functions()
        assert "function_name" in df.columns
        assert "runtime" in df.columns


class TestEBSVolumes:
    def test_count(self):
        df = generate_ebs_volumes()
        assert len(df) >= 1

    def test_volume_ids_unique(self):
        df = generate_ebs_volumes()
        assert df["volume_id"].is_unique


class TestInstancePricing:
    def test_returns_dataframe(self):
        df, real_count, synthetic_count = generate_instance_pricing()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_has_pricing_columns(self):
        df, _, _ = generate_instance_pricing()
        assert "instance_type" in df.columns
        assert "hourly_price_usd" in df.columns
