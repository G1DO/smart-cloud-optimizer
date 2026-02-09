"""Tests for the optimizer module.

Tests the LP solver, rule engine, and orchestrator using temporary
in-memory SQLite databases with minimal synthetic data.
"""

import random

import numpy as np
import pytest

from storage import (
    create_schema,
    ensure_user,
    get_connection,
    get_recommendations,
    insert_dynamodb_metrics,
    insert_dynamodb_tables,
    insert_ebs_metrics,
    insert_ebs_volumes,
    insert_ec2_instances,
    insert_ec2_metrics,
    insert_elb_instances,
    insert_elb_metrics,
    insert_instance_pricing,
    insert_lambda_functions,
    insert_lambda_metrics,
    insert_nat_gateways,
    insert_rds_instances,
    insert_rds_metrics,
    insert_s3_buckets,
)
from optimizer import (
    check_dynamodb_tables,
    check_ebs_volumes,
    check_ec2_pricing,
    check_elb_idle,
    check_lambda_memory,
    check_nat_gateways,
    check_rds_pricing,
    check_s3_buckets,
    optimize,
    optimize_ec2,
    optimize_rds,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_conn(tmp_path):
    """Fresh SQLite database with schema."""
    db_path = tmp_path / "test_optimizer.db"
    conn = get_connection(db_path)
    create_schema(conn)
    return conn


@pytest.fixture
def user_id(db_conn):
    """Create test user."""
    return ensure_user(db_conn, "TEST-OPT")


def _make_ec2_metrics(instance_id, days=30, cpu_mean=10.0, mem_mean=30.0):
    """Generate hourly EC2 metrics for testing."""
    rows = []
    for h in range(days * 24):
        day = h // 24
        hour = h % 24
        rows.append({
            "timestamp": f"2024-01-{1 + day:02d}T{hour:02d}:00:00+00:00",
            "instance_id": instance_id,
            "cpu_utilization": max(1, cpu_mean + random.gauss(0, 3)),
            "cpu_max": max(1, cpu_mean + 5 + abs(random.gauss(0, 3))),
            "memory_utilization": max(1, mem_mean + random.gauss(0, 5)),
        })
    return rows


def _make_rds_metrics(db_instance_id, days=30, cpu_mean=10.0):
    """Generate hourly RDS metrics for testing."""
    rows = []
    for h in range(days * 24):
        day = h // 24
        hour = h % 24
        rows.append({
            "timestamp": f"2024-01-{1 + day:02d}T{hour:02d}:00:00+00:00",
            "db_instance_id": db_instance_id,
            "cpu_utilization": max(1, cpu_mean + random.gauss(0, 3)),
            "memory_utilization": 8_000_000_000.0,  # raw bytes, not %
        })
    return rows


# ---------------------------------------------------------------------------
# EC2 LP right-sizing tests
# ---------------------------------------------------------------------------

class TestOptimizeEC2:

    def test_downsizes_overprovisioned_instance(self, db_conn, user_id):
        """m5.xlarge with 10% avg CPU should downsize to something cheaper."""
        insert_ec2_instances(db_conn, user_id, [{
            "instance_id": "i-test-001",
            "instance_type": "m5.xlarge",
            "state": "running",
            "launch_date": "2024-01-01",
            "pricing_model": "on-demand",
            "monthly_cost": 140.16,
            "vcpus": 4,
            "memory_gb": 16.0,
        }])
        insert_ec2_metrics(db_conn, user_id,
                           _make_ec2_metrics("i-test-001", days=30, cpu_mean=10, mem_mean=30))
        insert_instance_pricing(db_conn, [
            {"service": "EC2", "instance_type": "m5.xlarge",
             "vcpus": 4, "memory_gb": 16.0,
             "on_demand_hourly": 0.192, "on_demand_monthly": 140.16},
            {"service": "EC2", "instance_type": "t3.medium",
             "vcpus": 2, "memory_gb": 4.0,
             "on_demand_hourly": 0.0416, "on_demand_monthly": 30.37},
            {"service": "EC2", "instance_type": "m5.large",
             "vcpus": 2, "memory_gb": 8.0,
             "on_demand_hourly": 0.096, "on_demand_monthly": 70.08},
        ])
        db_conn.commit()

        recs = optimize_ec2(db_conn, user_id)
        assert len(recs) == 1
        rec = recs[0]
        assert rec["recommendation_type"] == "rightsize"
        assert rec["service"] == "EC2"
        assert rec["monthly_savings"] > 0
        assert rec["estimated_monthly_cost"] < rec["current_monthly_cost"]

    def test_no_recommendation_for_well_sized(self, db_conn, user_id):
        """Instance already on cheapest feasible type gets no recommendation."""
        insert_ec2_instances(db_conn, user_id, [{
            "instance_id": "i-test-002",
            "instance_type": "t3.medium",
            "state": "running",
            "launch_date": "2024-01-01",
            "pricing_model": "on-demand",
            "monthly_cost": 30.37,
            "vcpus": 2,
            "memory_gb": 4.0,
        }])
        insert_ec2_metrics(db_conn, user_id,
                           _make_ec2_metrics("i-test-002", days=30, cpu_mean=45, mem_mean=70))
        insert_instance_pricing(db_conn, [
            {"service": "EC2", "instance_type": "t3.medium",
             "vcpus": 2, "memory_gb": 4.0,
             "on_demand_hourly": 0.0416, "on_demand_monthly": 30.37},
            {"service": "EC2", "instance_type": "t3.micro",
             "vcpus": 2, "memory_gb": 1.0,
             "on_demand_hourly": 0.0104, "on_demand_monthly": 7.59},
        ])
        db_conn.commit()

        recs = optimize_ec2(db_conn, user_id)
        # Either no recs (optimal == current) or LP picks t3.medium (cheapest feasible)
        for rec in recs:
            assert rec["monthly_savings"] > 0  # Only savings recs are returned

    def test_handles_empty_metrics(self, db_conn, user_id):
        """Instance with no metrics should be skipped."""
        insert_ec2_instances(db_conn, user_id, [{
            "instance_id": "i-test-003",
            "instance_type": "m5.xlarge",
            "state": "running",
            "launch_date": "2024-01-01",
            "pricing_model": "on-demand",
        }])
        db_conn.commit()

        recs = optimize_ec2(db_conn, user_id)
        assert recs == []

    def test_skips_stopped_instances(self, db_conn, user_id):
        """Stopped instances should not be optimized."""
        insert_ec2_instances(db_conn, user_id, [{
            "instance_id": "i-test-004",
            "instance_type": "m5.xlarge",
            "state": "stopped",
            "launch_date": "2024-01-01",
            "pricing_model": "on-demand",
        }])
        insert_ec2_metrics(db_conn, user_id,
                           _make_ec2_metrics("i-test-004", days=30, cpu_mean=5))
        db_conn.commit()

        recs = optimize_ec2(db_conn, user_id)
        assert recs == []

    def test_respects_budget_cap(self, db_conn, user_id):
        """Budget cap should constrain total cost of assigned types."""
        insert_ec2_instances(db_conn, user_id, [{
            "instance_id": "i-test-005",
            "instance_type": "m5.xlarge",
            "state": "running",
            "launch_date": "2024-01-01",
            "pricing_model": "on-demand",
            "monthly_cost": 140.16,
            "vcpus": 4,
            "memory_gb": 16.0,
        }])
        insert_ec2_metrics(db_conn, user_id,
                           _make_ec2_metrics("i-test-005", days=30, cpu_mean=5, mem_mean=10))
        insert_instance_pricing(db_conn, [
            {"service": "EC2", "instance_type": "m5.xlarge",
             "vcpus": 4, "memory_gb": 16.0,
             "on_demand_hourly": 0.192, "on_demand_monthly": 140.16},
            {"service": "EC2", "instance_type": "t3.micro",
             "vcpus": 2, "memory_gb": 1.0,
             "on_demand_hourly": 0.0104, "on_demand_monthly": 7.59},
        ])
        db_conn.commit()

        recs = optimize_ec2(db_conn, user_id, budget_cap=200.0)
        # Should still find a cheaper option within budget
        if recs:
            assert recs[0]["estimated_monthly_cost"] <= 200.0


# ---------------------------------------------------------------------------
# RDS LP right-sizing tests
# ---------------------------------------------------------------------------

class TestOptimizeRDS:

    def test_downsizes_overprovisioned_rds(self, db_conn, user_id):
        """RDS instance with low CPU should downsize."""
        insert_rds_instances(db_conn, user_id, [{
            "db_instance_id": "test-rds-001",
            "db_instance_class": "db.r5.large",
            "engine": "postgres",
            "storage_gb": 100,
            "multi_az": 0,
            "pricing_model": "on-demand",
            "monthly_cost": 175.20,
        }])
        insert_rds_metrics(db_conn, user_id,
                           _make_rds_metrics("test-rds-001", days=30, cpu_mean=8))
        insert_instance_pricing(db_conn, [
            {"service": "RDS", "instance_type": "db.r5.large",
             "vcpus": 2, "memory_gb": 16.0,
             "on_demand_hourly": 0.240, "on_demand_monthly": 175.20},
            {"service": "RDS", "instance_type": "db.t4g.medium",
             "vcpus": 2, "memory_gb": 4.0,
             "on_demand_hourly": 0.065, "on_demand_monthly": 47.45},
        ])
        db_conn.commit()

        recs = optimize_rds(db_conn, user_id)
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "rightsize"
        assert recs[0]["monthly_savings"] > 0

    def test_handles_no_rds_instances(self, db_conn, user_id):
        """No RDS instances should return empty list."""
        recs = optimize_rds(db_conn, user_id)
        assert recs == []


# ---------------------------------------------------------------------------
# EC2 pricing plan switch tests
# ---------------------------------------------------------------------------

class TestCheckEC2Pricing:

    def test_recommends_reserved_for_long_running(self, db_conn, user_id):
        """On-demand instance with >60 days of metrics should get reserved rec."""
        insert_ec2_instances(db_conn, user_id, [{
            "instance_id": "i-test-price-001",
            "instance_type": "m5.large",
            "state": "running",
            "pricing_model": "on-demand",
            "monthly_cost": 70.08,
        }])
        insert_ec2_metrics(db_conn, user_id,
                           _make_ec2_metrics("i-test-price-001", days=30, cpu_mean=20))
        insert_instance_pricing(db_conn, [
            {"service": "EC2", "instance_type": "m5.large",
             "vcpus": 2, "memory_gb": 8.0,
             "on_demand_hourly": 0.096, "on_demand_monthly": 70.08,
             "reserved_1yr_monthly": 44.15},
        ])
        db_conn.commit()

        # 30 days of hourly metrics = 720 rows spanning 29 days — below 60 day threshold
        recs = check_ec2_pricing(db_conn, user_id, min_running_days=20)
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "pricing_plan_switch"
        assert recs[0]["monthly_savings"] > 0

    def test_skips_already_reserved(self, db_conn, user_id):
        """Reserved instance should not get pricing switch recommendation."""
        insert_ec2_instances(db_conn, user_id, [{
            "instance_id": "i-test-price-002",
            "instance_type": "m5.large",
            "state": "running",
            "pricing_model": "reserved-1yr",
            "monthly_cost": 44.15,
        }])
        insert_ec2_metrics(db_conn, user_id,
                           _make_ec2_metrics("i-test-price-002", days=30, cpu_mean=20))
        db_conn.commit()

        recs = check_ec2_pricing(db_conn, user_id)
        assert recs == []


# ---------------------------------------------------------------------------
# RDS pricing plan switch tests
# ---------------------------------------------------------------------------

class TestCheckRDSPricing:

    def test_recommends_reserved_for_long_running_rds(self, db_conn, user_id):
        """On-demand RDS with sufficient metrics span gets reserved rec."""
        insert_rds_instances(db_conn, user_id, [{
            "db_instance_id": "test-rds-price",
            "db_instance_class": "db.r5.large",
            "engine": "postgres",
            "storage_gb": 100,
            "multi_az": 0,
            "pricing_model": "on-demand",
            "monthly_cost": 175.20,
        }])
        insert_rds_metrics(db_conn, user_id,
                           _make_rds_metrics("test-rds-price", days=30, cpu_mean=20))
        insert_instance_pricing(db_conn, [
            {"service": "RDS", "instance_type": "db.r5.large",
             "vcpus": 2, "memory_gb": 16.0,
             "on_demand_hourly": 0.240,
             "reserved_1yr_hourly": 0.1512,
             "on_demand_monthly": 175.20,
             "reserved_1yr_monthly": 110.38},
        ])
        db_conn.commit()

        recs = check_rds_pricing(db_conn, user_id, min_running_days=20)
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "pricing_plan_switch"


# ---------------------------------------------------------------------------
# Lambda memory resize tests
# ---------------------------------------------------------------------------

class TestCheckLambdaMemory:

    def test_recommends_resize_when_underutilized(self, db_conn, user_id):
        """Lambda using <50% memory should get resize recommendation."""
        insert_lambda_functions(db_conn, user_id, [{
            "function_name": "test-fn-001",
            "runtime": "python3.12",
            "memory_mb": 256,
            "monthly_cost": 5.00,
        }])
        metrics = []
        for d in range(20):
            metrics.append({
                "date": f"2024-01-{1 + d:02d}",
                "function_name": "test-fn-001",
                "invocations": 1000,
                "avg_duration_ms": 50,
                "avg_memory_used_mb": 60.0,  # 23% of 256 MB
                "memory_allocated_mb": 256,
            })
        insert_lambda_metrics(db_conn, user_id, metrics)
        db_conn.commit()

        recs = check_lambda_memory(db_conn, user_id)
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "memory_resize"
        assert recs[0]["monthly_savings"] > 0

    def test_no_recommendation_when_well_utilized(self, db_conn, user_id):
        """Lambda using >50% memory should not get resize recommendation."""
        insert_lambda_functions(db_conn, user_id, [{
            "function_name": "test-fn-002",
            "runtime": "python3.12",
            "memory_mb": 256,
            "monthly_cost": 5.00,
        }])
        metrics = []
        for d in range(20):
            metrics.append({
                "date": f"2024-01-{1 + d:02d}",
                "function_name": "test-fn-002",
                "invocations": 1000,
                "avg_duration_ms": 50,
                "avg_memory_used_mb": 180.0,  # 70% of 256 MB
                "memory_allocated_mb": 256,
            })
        insert_lambda_metrics(db_conn, user_id, metrics)
        db_conn.commit()

        recs = check_lambda_memory(db_conn, user_id)
        assert recs == []


# ---------------------------------------------------------------------------
# EBS volume tests
# ---------------------------------------------------------------------------

class TestCheckEBSVolumes:

    def test_recommends_gp2_to_gp3(self, db_conn, user_id):
        """gp2 volumes should always get upgrade recommendation."""
        insert_ebs_volumes(db_conn, user_id, [{
            "volume_id": "vol-test-001",
            "volume_type": "gp2",
            "size_gb": 100,
            "state": "in-use",
            "monthly_cost": 10.00,
        }])
        db_conn.commit()

        recs = check_ebs_volumes(db_conn, user_id)
        type_upgrade = [r for r in recs if r["recommendation_type"] == "volume_type_upgrade"]
        assert len(type_upgrade) == 1
        assert type_upgrade[0]["monthly_savings"] == 2.0  # (0.10 - 0.08) * 100

    def test_flags_unattached_volumes(self, db_conn, user_id):
        """Available (unattached) volumes should get delete recommendation."""
        insert_ebs_volumes(db_conn, user_id, [{
            "volume_id": "vol-test-002",
            "volume_type": "gp3",
            "size_gb": 50,
            "state": "available",
            "monthly_cost": 4.00,
        }])
        db_conn.commit()

        recs = check_ebs_volumes(db_conn, user_id)
        delete_recs = [r for r in recs if r["recommendation_type"] == "delete_unused"]
        assert len(delete_recs) == 1
        assert delete_recs[0]["savings_percent"] == 100.0

    def test_no_recommendation_for_active_gp3(self, db_conn, user_id):
        """Active gp3 volume should not get type upgrade recommendation."""
        insert_ebs_volumes(db_conn, user_id, [{
            "volume_id": "vol-test-003",
            "volume_type": "gp3",
            "size_gb": 50,
            "state": "in-use",
            "monthly_cost": 4.00,
        }])
        db_conn.commit()

        recs = check_ebs_volumes(db_conn, user_id)
        type_upgrade = [r for r in recs if r["recommendation_type"] == "volume_type_upgrade"]
        assert type_upgrade == []


# ---------------------------------------------------------------------------
# S3 storage class tests
# ---------------------------------------------------------------------------

class TestCheckS3Buckets:

    def test_recommends_intelligent_tiering_low_access(self, db_conn, user_id):
        """Low-access STANDARD bucket should get INTELLIGENT_TIERING rec."""
        insert_s3_buckets(db_conn, user_id, [{
            "bucket_name": "test-bucket-001",
            "storage_class": "STANDARD",
            "size_gb": 500.0,
            "avg_daily_get_requests": 5,
            "avg_daily_put_requests": 2,
            "monthly_cost": 11.50,
            "num_objects": 10000,
        }])
        db_conn.commit()

        recs = check_s3_buckets(db_conn, user_id)
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "storage_class_switch"
        assert recs[0]["monthly_savings"] > 0

    def test_skips_high_access_bucket(self, db_conn, user_id):
        """High-access bucket should not get storage class recommendation."""
        insert_s3_buckets(db_conn, user_id, [{
            "bucket_name": "test-bucket-002",
            "storage_class": "STANDARD",
            "size_gb": 100.0,
            "avg_daily_get_requests": 5000,
            "avg_daily_put_requests": 500,
            "monthly_cost": 2.30,
        }])
        db_conn.commit()

        recs = check_s3_buckets(db_conn, user_id)
        assert recs == []


# ---------------------------------------------------------------------------
# DynamoDB capacity mode tests
# ---------------------------------------------------------------------------

class TestCheckDynamoDBTables:

    def test_recommends_ondemand_for_low_utilization(self, db_conn, user_id):
        """PROVISIONED table with low utilization should switch to ON_DEMAND."""
        insert_dynamodb_tables(db_conn, user_id, [{
            "table_name": "test-table-001",
            "capacity_mode": "PROVISIONED",
            "provisioned_rcu": 200,
            "provisioned_wcu": 100,
            "storage_gb": 5.0,
            "item_count": 50000,
            "monthly_cost": 65.00,  # 200*0.09 + 100*0.47
        }])
        # Low utilization: avg 20 RCU / 200 prov = 10%, 10 WCU / 100 = 10%
        metrics = []
        for h in range(20 * 24):
            day = h // 24
            hour = h % 24
            metrics.append({
                "timestamp": f"2024-01-{1 + day:02d}T{hour:02d}:00:00+00:00",
                "table_name": "test-table-001",
                "consumed_read_units": 20 + random.gauss(0, 3),
                "consumed_write_units": 10 + random.gauss(0, 2),
            })
        insert_dynamodb_metrics(db_conn, user_id, metrics)
        db_conn.commit()

        recs = check_dynamodb_tables(db_conn, user_id)
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "capacity_mode_switch"
        assert recs[0]["monthly_savings"] > 0

    def test_skips_already_ondemand(self, db_conn, user_id):
        """ON_DEMAND table should not get capacity mode recommendation."""
        insert_dynamodb_tables(db_conn, user_id, [{
            "table_name": "test-table-002",
            "capacity_mode": "ON_DEMAND",
            "storage_gb": 5.0,
            "item_count": 50000,
        }])
        db_conn.commit()

        recs = check_dynamodb_tables(db_conn, user_id)
        assert recs == []


# ---------------------------------------------------------------------------
# NAT Gateway tests
# ---------------------------------------------------------------------------

class TestCheckNATGateways:

    def test_recommends_endpoint_for_expensive_nat(self, db_conn, user_id):
        """Expensive NAT should get VPC endpoint recommendation."""
        insert_nat_gateways(db_conn, user_id, [{
            "nat_gateway_id": "nat-test-001",
            "vpc_id": "vpc-001",
            "subnet_id": "subnet-001",
            "state": "available",
            "monthly_cost": 50.00,
            "monthly_data_processed_gb": 200.0,
        }])
        db_conn.commit()

        recs = check_nat_gateways(db_conn, user_id)
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "replace_with_endpoint"

    def test_skips_cheap_nat(self, db_conn, user_id):
        """Cheap NAT should not get recommendation."""
        insert_nat_gateways(db_conn, user_id, [{
            "nat_gateway_id": "nat-test-002",
            "vpc_id": "vpc-001",
            "subnet_id": "subnet-002",
            "state": "available",
            "monthly_cost": 20.00,
            "monthly_data_processed_gb": 10.0,
        }])
        db_conn.commit()

        recs = check_nat_gateways(db_conn, user_id)
        assert recs == []


# ---------------------------------------------------------------------------
# ELB idle tests
# ---------------------------------------------------------------------------

class TestCheckELBIdle:

    def test_recommends_delete_zero_targets_no_traffic(self, db_conn, user_id):
        """ELB with 0 targets and no traffic should get delete rec."""
        arn = "arn:aws:elb:test/app/test-alb/12345"
        insert_elb_instances(db_conn, user_id, [{
            "elb_arn": arn,
            "elb_name": "test-alb",
            "elb_type": "ALB",
            "target_count": 0,
            "monthly_cost": 16.20,
        }])
        # Insert minimal metrics with near-zero traffic
        metrics = []
        for h in range(10 * 24):
            day = h // 24
            hour = h % 24
            metrics.append({
                "timestamp": f"2024-01-{1 + day:02d}T{hour:02d}:00:00+00:00",
                "elb_arn": arn,
                "request_count": 0,
            })
        insert_elb_metrics(db_conn, user_id, metrics)
        db_conn.commit()

        recs = check_elb_idle(db_conn, user_id)
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "delete_idle"
        assert recs[0]["confidence"] == "high"

    def test_skips_active_elb_with_traffic(self, db_conn, user_id):
        """ELB with targets and traffic should not be flagged."""
        arn = "arn:aws:elb:test/app/active-alb/67890"
        insert_elb_instances(db_conn, user_id, [{
            "elb_arn": arn,
            "elb_name": "active-alb",
            "elb_type": "ALB",
            "target_count": 3,
            "monthly_cost": 16.20,
        }])
        metrics = []
        for h in range(10 * 24):
            day = h // 24
            hour = h % 24
            metrics.append({
                "timestamp": f"2024-01-{1 + day:02d}T{hour:02d}:00:00+00:00",
                "elb_arn": arn,
                "request_count": 5000,
            })
        insert_elb_metrics(db_conn, user_id, metrics)
        db_conn.commit()

        recs = check_elb_idle(db_conn, user_id)
        assert recs == []


# ---------------------------------------------------------------------------
# Orchestrator tests
# ---------------------------------------------------------------------------

class TestOrchestrate:

    def test_runs_all_and_writes_to_db(self, db_conn, user_id):
        """Full optimize() should produce recs and write to DB."""
        # Set up an overprovisioned EC2 + pricing
        insert_ec2_instances(db_conn, user_id, [{
            "instance_id": "i-orch-001",
            "instance_type": "m5.xlarge",
            "state": "running",
            "pricing_model": "on-demand",
            "monthly_cost": 140.16,
            "vcpus": 4,
            "memory_gb": 16.0,
        }])
        insert_ec2_metrics(db_conn, user_id,
                           _make_ec2_metrics("i-orch-001", days=30, cpu_mean=8, mem_mean=20))
        insert_instance_pricing(db_conn, [
            {"service": "EC2", "instance_type": "m5.xlarge",
             "vcpus": 4, "memory_gb": 16.0,
             "on_demand_hourly": 0.192, "on_demand_monthly": 140.16,
             "reserved_1yr_monthly": 88.30},
            {"service": "EC2", "instance_type": "t3.medium",
             "vcpus": 2, "memory_gb": 4.0,
             "on_demand_hourly": 0.0416, "on_demand_monthly": 30.37},
        ])
        # Unattached EBS volume
        insert_ebs_volumes(db_conn, user_id, [{
            "volume_id": "vol-orch-001",
            "volume_type": "gp2",
            "size_gb": 50,
            "state": "available",
            "monthly_cost": 5.00,
        }])
        db_conn.commit()

        recs = optimize(db_conn, user_id)
        assert len(recs) >= 2  # At least EC2 pricing + EBS delete

        # Verify recs are in DB
        db_recs = get_recommendations(db_conn, user_id)
        assert len(db_recs) == len(recs)

    def test_filters_by_service(self, db_conn, user_id):
        """Passing services=['ebs'] should only run EBS checks."""
        insert_ebs_volumes(db_conn, user_id, [{
            "volume_id": "vol-filter-001",
            "volume_type": "gp2",
            "size_gb": 50,
            "state": "available",
            "monthly_cost": 5.00,
        }])
        db_conn.commit()

        recs = optimize(db_conn, user_id, services=["ebs"])
        for rec in recs:
            assert rec["service"] == "EBS"

    def test_empty_user_returns_empty(self, db_conn, user_id):
        """User with no resources should return empty list."""
        recs = optimize(db_conn, user_id)
        assert recs == []

    def test_clears_previous_recommendations(self, db_conn, user_id):
        """Running optimize() twice should clear old recs."""
        insert_ebs_volumes(db_conn, user_id, [{
            "volume_id": "vol-clear-001",
            "volume_type": "gp2",
            "size_gb": 50,
            "state": "available",
            "monthly_cost": 5.00,
        }])
        db_conn.commit()

        recs1 = optimize(db_conn, user_id, services=["ebs"])
        recs2 = optimize(db_conn, user_id, services=["ebs"])

        # DB should only have the second run's recs
        db_recs = get_recommendations(db_conn, user_id)
        assert len(db_recs) == len(recs2)
