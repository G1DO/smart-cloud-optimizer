"""Tests for data_generation.synthetic"""
import pandas as pd
import numpy as np

from data_generation.synthetic import (
    generate_daily_costs,
    generate_service_costs,
    generate_service_region_costs,
    generate_ec2_instances,
    generate_ec2_metrics,
    generate_rds_instances,
    generate_rds_metrics,
    generate_s3_buckets,
    generate_lambda_functions,
    generate_ebs_volumes,
    generate_instance_pricing,
    generate_elasticache_nodes,
    generate_elasticache_metrics,
    generate_ecs_services,
    generate_ecs_metrics,
    generate_dynamodb_tables,
    generate_dynamodb_metrics,
    generate_nat_gateways,
    generate_nat_gateway_metrics,
    generate_elb_instances,
    generate_elb_metrics,
    generate_ebs_metrics,
    generate_lambda_metrics,
    generate_s3_metrics,
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


class TestServiceRegionCosts:
    def test_has_region_column(self):
        svc = generate_service_costs(days=30, seed=1)
        df = generate_service_region_costs(svc, seed=1)
        assert "region" in df.columns

    def test_more_rows_than_service_costs(self):
        svc = generate_service_costs(days=30, seed=1)
        df = generate_service_region_costs(svc, seed=1)
        assert len(df) >= len(svc)

    def test_no_negative_costs(self):
        svc = generate_service_costs(days=30, seed=1)
        df = generate_service_region_costs(svc, seed=1)
        assert (df["cost_amount"] >= 0).all()

    def test_required_columns(self):
        svc = generate_service_costs(days=30, seed=1)
        df = generate_service_region_costs(svc, seed=1)
        for col in ["account_id", "date", "service_name", "region", "cost_amount", "currency"]:
            assert col in df.columns


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


class TestElastiCacheNodes:
    def test_count(self):
        df = generate_elasticache_nodes()
        assert len(df) == 3

    def test_required_columns(self):
        df = generate_elasticache_nodes()
        for col in ["cache_cluster_id", "cache_node_type", "engine"]:
            assert col in df.columns

    def test_engines(self):
        df = generate_elasticache_nodes()
        assert set(df["engine"]) == {"redis", "memcached"}


class TestElastiCacheMetrics:
    def test_has_rows(self):
        df = generate_elasticache_metrics(days=3, seed=1)
        assert len(df) > 0

    def test_cache_hit_ratio(self):
        df = generate_elasticache_metrics(days=7, seed=1)
        total_hits = df["cache_hits"].sum()
        total_misses = df["cache_misses"].sum()
        ratio = total_hits / (total_hits + total_misses)
        assert ratio > 0.90

    def test_cpu_range(self):
        df = generate_elasticache_metrics(days=7, seed=1)
        assert (df["cpu_util_avg"] >= 0).all()
        assert (df["cpu_util_avg"] <= 100).all()


class TestECSServices:
    def test_count(self):
        df = generate_ecs_services()
        assert len(df) == 4

    def test_required_columns(self):
        df = generate_ecs_services()
        for col in ["service_name", "cluster_name", "cpu", "memory_mb"]:
            assert col in df.columns


class TestECSMetrics:
    def test_has_rows(self):
        df = generate_ecs_metrics(days=3, seed=1)
        assert len(df) > 0

    def test_cpu_range(self):
        df = generate_ecs_metrics(days=7, seed=1)
        assert (df["cpu_utilization_avg"] >= 0).all()
        assert (df["cpu_utilization_avg"] <= 100).all()


class TestDynamoDBTables:
    def test_count(self):
        df = generate_dynamodb_tables()
        assert len(df) == 3

    def test_capacity_modes(self):
        df = generate_dynamodb_tables()
        assert "ON_DEMAND" in df["capacity_mode"].values
        assert "PROVISIONED" in df["capacity_mode"].values


class TestDynamoDBMetrics:
    def test_has_rows(self):
        df = generate_dynamodb_metrics(days=3, seed=1)
        assert len(df) > 0

    def test_no_negative_units(self):
        df = generate_dynamodb_metrics(days=7, seed=1)
        assert (df["consumed_read_units_avg"] >= 0).all()
        assert (df["consumed_write_units_avg"] >= 0).all()


class TestNATGateways:
    def test_count(self):
        df = generate_nat_gateways()
        assert len(df) == 2

    def test_required_columns(self):
        df = generate_nat_gateways()
        for col in ["nat_gateway_id", "vpc_id", "subnet_id", "state"]:
            assert col in df.columns


class TestNATGatewayMetrics:
    def test_has_rows(self):
        df = generate_nat_gateway_metrics(days=3, seed=1)
        assert len(df) > 0

    def test_no_negative_bytes(self):
        df = generate_nat_gateway_metrics(days=7, seed=1)
        assert (df["bytes_in_avg"] >= 0).all()
        assert (df["bytes_out_avg"] >= 0).all()


class TestELBInstances:
    def test_count(self):
        df = generate_elb_instances()
        assert len(df) == 3

    def test_required_columns(self):
        df = generate_elb_instances()
        for col in ["load_balancer_arn", "load_balancer_name", "type"]:
            assert col in df.columns


class TestELBMetrics:
    def test_has_rows(self):
        df = generate_elb_metrics(days=3, seed=1)
        assert len(df) > 0

    def test_http_codes_non_negative(self):
        df = generate_elb_metrics(days=7, seed=1)
        for col in ["http_2xx", "http_3xx", "http_4xx", "http_5xx"]:
            assert (df[col] >= 0).all()


class TestEBSMetrics:
    def test_has_rows(self):
        df = generate_ebs_metrics(days=3, seed=1)
        assert len(df) > 0

    def test_multiple_volumes(self):
        df = generate_ebs_metrics(days=3, seed=1)
        assert df["volume_id"].nunique() == 8

    def test_no_negative_ops(self):
        df = generate_ebs_metrics(days=7, seed=1)
        assert (df["read_ops_avg"] >= 0).all()
        assert (df["write_ops_avg"] >= 0).all()


class TestLambdaMetrics:
    def test_has_rows(self):
        df = generate_lambda_metrics(days=7, seed=1)
        assert len(df) > 0

    def test_multiple_functions(self):
        df = generate_lambda_metrics(days=7, seed=1)
        assert df["function_name"].nunique() == 4

    def test_no_negative_invocations(self):
        df = generate_lambda_metrics(days=7, seed=1)
        assert (df["invocations"] >= 0).all()
        assert (df["errors"] >= 0).all()


class TestS3Metrics:
    def test_has_rows(self):
        df = generate_s3_metrics(days=7, seed=1)
        assert len(df) > 0

    def test_multiple_buckets(self):
        df = generate_s3_metrics(days=7, seed=1)
        assert df["bucket_name"].nunique() == 4

    def test_positive_sizes(self):
        df = generate_s3_metrics(days=7, seed=1)
        assert (df["bucket_size_bytes"] >= 0).all()
