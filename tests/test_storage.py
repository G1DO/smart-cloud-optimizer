"""Tests for storage.db — schema creation and insert/query API."""
import sqlite3
from pathlib import Path

import pytest

from storage.db import (
    create_schema,
    clear_user_data,
    ensure_user,
    get_connection,
    insert_daily_costs,
    insert_service_costs,
    insert_service_region_costs,
    insert_ec2_instances,
    insert_ec2_metrics,
    insert_rds_instances,
    insert_rds_metrics,
    insert_elasticache_nodes,
    insert_elasticache_metrics,
    insert_ecs_services,
    insert_ecs_metrics,
    insert_lambda_functions,
    insert_lambda_metrics,
    insert_ebs_volumes,
    insert_ebs_metrics,
    insert_s3_buckets,
    insert_s3_metrics,
    insert_dynamodb_tables,
    insert_dynamodb_metrics,
    insert_nat_gateways,
    insert_nat_gateway_metrics,
    insert_elb_instances,
    insert_elb_metrics,
    insert_instance_pricing,
    insert_ai_recommendations,
    get_daily_costs,
    get_service_costs,
    get_ec2_instances,
    get_ec2_metrics,
)


@pytest.fixture
def db_conn(tmp_path):
    """Create an in-memory DB with schema."""
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    create_schema(conn)
    return conn


@pytest.fixture
def user_id(db_conn):
    """Create a test user and return user_id."""
    return ensure_user(db_conn, "123456789012")


class TestCreateSchema:
    def test_creates_all_tables(self, db_conn):
        tables = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {t[0] for t in tables}
        expected = {
            "users", "aws_connections", "daily_costs", "service_costs",
            "service_region_costs",
            "ec2_metrics", "rds_metrics", "elasticache_metrics", "ecs_metrics",
            "lambda_metrics", "dynamodb_metrics", "s3_metrics",
            "ebs_metrics", "nat_gateway_metrics", "elb_metrics",
            "ec2_instances", "rds_instances", "elasticache_nodes", "ecs_services",
            "lambda_functions", "ebs_volumes", "s3_buckets", "dynamodb_tables",
            "nat_gateways", "elb_instances",
            "instance_pricing", "ai_recommendations", "forecasts",
            "recommendations", "anomalies",
        }
        assert expected.issubset(table_names)

    def test_ec2_instances_has_columns(self, db_conn):
        cols = {row[1] for row in db_conn.execute(
            "PRAGMA table_info(ec2_instances)"
        ).fetchall()}
        for col in ("private_ip", "public_ip", "vpc_id", "subnet_id", "ami_id", "tags"):
            assert col in cols

    def test_ec2_metrics_has_columns(self, db_conn):
        cols = {row[1] for row in db_conn.execute(
            "PRAGMA table_info(ec2_metrics)"
        ).fetchall()}
        for col in ("cpu_max", "disk_read_ops", "disk_write_ops"):
            assert col in cols


class TestEnsureUser:
    def test_creates_user(self, db_conn):
        uid = ensure_user(db_conn, "123456789012")
        assert uid == "aws-123456789012"
        row = db_conn.execute(
            "SELECT email, user_type FROM users WHERE user_id = ?", (uid,)
        ).fetchone()
        assert row[0] == "123456789012@aws.local"
        assert row[1] == "active"

    def test_idempotent(self, db_conn):
        uid1 = ensure_user(db_conn, "111")
        uid2 = ensure_user(db_conn, "111")
        assert uid1 == uid2
        count = db_conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert count == 1


class TestClearUserData:
    def test_clears_costs(self, db_conn, user_id):
        insert_daily_costs(db_conn, user_id, [
            {"date": "2024-01-01", "total_cost": 10.0},
        ])
        db_conn.commit()
        assert db_conn.execute("SELECT COUNT(*) FROM daily_costs").fetchone()[0] == 1
        clear_user_data(db_conn, user_id)
        db_conn.commit()
        assert db_conn.execute("SELECT COUNT(*) FROM daily_costs").fetchone()[0] == 0


class TestInsertDailyCosts:
    def test_insert_and_query(self, db_conn, user_id):
        rows = [
            {"date": "2024-01-01", "total_cost": 10.5},
            {"date": "2024-01-02", "total_cost": 20.0},
        ]
        count = insert_daily_costs(db_conn, user_id, rows)
        assert count == 2

        result = get_daily_costs(db_conn, user_id)
        assert len(result) == 2
        assert result[0]["total_cost"] == 10.5

    def test_date_filter(self, db_conn, user_id):
        rows = [
            {"date": "2024-01-01", "total_cost": 10.0},
            {"date": "2024-01-15", "total_cost": 20.0},
            {"date": "2024-02-01", "total_cost": 30.0},
        ]
        insert_daily_costs(db_conn, user_id, rows)
        result = get_daily_costs(db_conn, user_id, start_date="2024-01-10")
        assert len(result) == 2

    def test_upsert(self, db_conn, user_id):
        insert_daily_costs(db_conn, user_id, [{"date": "2024-01-01", "total_cost": 10.0}])
        insert_daily_costs(db_conn, user_id, [{"date": "2024-01-01", "total_cost": 99.0}])
        result = get_daily_costs(db_conn, user_id)
        assert len(result) == 1
        assert result[0]["total_cost"] == 99.0


class TestInsertServiceCosts:
    def test_insert_and_query(self, db_conn, user_id):
        rows = [
            {"date": "2024-01-01", "service": "EC2", "daily_cost": 50.0},
            {"date": "2024-01-01", "service": "Lambda", "daily_cost": 5.0},
        ]
        count = insert_service_costs(db_conn, user_id, rows)
        assert count == 2
        result = get_service_costs(db_conn, user_id)
        assert len(result) == 2


class TestInsertEC2Instances:
    def test_insert_and_query(self, db_conn, user_id):
        rows = [
            {
                "instance_id": "i-abc123",
                "instance_type": "m5.xlarge",
                "state": "running",
                "launch_date": "2024-01-01",
                "region": "us-east-1",
            },
        ]
        count = insert_ec2_instances(db_conn, user_id, rows)
        assert count == 1
        result = get_ec2_instances(db_conn, user_id)
        assert len(result) == 1
        assert result[0]["instance_id"] == "i-abc123"
        assert result[0]["vcpus"] == 4  # from INSTANCE_SPECS


class TestInsertEC2Metrics:
    def test_insert_and_query(self, db_conn, user_id):
        # Need an instance first for the foreign key
        insert_ec2_instances(db_conn, user_id, [
            {"instance_id": "i-abc123", "instance_type": "t3.micro",
             "state": "running", "launch_date": "2024-01-01", "region": "us-east-1"},
        ])
        rows = [
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "instance_id": "i-abc123",
                "cpu_utilization": 25.0,
                "cpu_max": 40.0,
                "network_in_kbps": 1000,
                "network_out_kbps": 500,
            },
        ]
        count = insert_ec2_metrics(db_conn, user_id, rows)
        assert count == 1
        result = get_ec2_metrics(db_conn, user_id, instance_id="i-abc123")
        assert len(result) == 1
        assert result[0]["cpu_utilization"] == 25.0


class TestInsertRDSInstances:
    def test_insert(self, db_conn, user_id):
        rows = [{"db_instance_id": "prod-pg", "db_instance_class": "db.r5.large",
                 "engine": "postgres", "storage_gb": 100}]
        assert insert_rds_instances(db_conn, user_id, rows) == 1


class TestInsertElastiCacheNodes:
    def test_insert(self, db_conn, user_id):
        rows = [{"cache_cluster_id": "prod-redis", "cache_node_type": "cache.r5.large",
                 "engine": "redis"}]
        assert insert_elasticache_nodes(db_conn, user_id, rows) == 1


class TestInsertECSServices:
    def test_insert(self, db_conn, user_id):
        rows = [{"service_name": "api", "cluster_name": "prod",
                 "cpu": 512, "memory_mb": 1024}]
        assert insert_ecs_services(db_conn, user_id, rows) == 1


class TestInsertLambdaFunctions:
    def test_insert(self, db_conn, user_id):
        rows = [{"function_name": "handler", "runtime": "python3.11"}]
        assert insert_lambda_functions(db_conn, user_id, rows) == 1


class TestInsertEBSVolumes:
    def test_insert(self, db_conn, user_id):
        rows = [{"volume_id": "vol-001", "volume_type": "gp3", "size_gb": 100}]
        assert insert_ebs_volumes(db_conn, user_id, rows) == 1


class TestInsertS3Buckets:
    def test_insert(self, db_conn, user_id):
        rows = [{"bucket_name": "my-bucket"}]
        assert insert_s3_buckets(db_conn, user_id, rows) == 1


class TestInsertDynamoDBTables:
    def test_insert(self, db_conn, user_id):
        rows = [{"table_name": "sessions", "capacity_mode": "ON_DEMAND"}]
        assert insert_dynamodb_tables(db_conn, user_id, rows) == 1


class TestInsertNATGateways:
    def test_insert(self, db_conn, user_id):
        rows = [{"nat_gateway_id": "nat-001", "vpc_id": "vpc-001", "subnet_id": "sub-001"}]
        assert insert_nat_gateways(db_conn, user_id, rows) == 1


class TestInsertELBInstances:
    def test_insert(self, db_conn, user_id):
        rows = [{"elb_arn": "arn:aws:elb:test", "elb_name": "my-alb",
                 "elb_type": "ALB"}]
        assert insert_elb_instances(db_conn, user_id, rows) == 1


class TestInsertInstancePricing:
    def test_insert(self, db_conn):
        rows = [{"service": "EC2", "instance_type": "t3.micro",
                 "on_demand_hourly": 0.0104, "on_demand_monthly": 7.59}]
        assert insert_instance_pricing(db_conn, rows) == 1


class TestInsertAIRecommendations:
    def test_insert(self, db_conn, user_id):
        rows = [{
            "app_type": "Web App",
            "prompt_text": "Web app with 5000 users",
            "recommended_setup": "t3.medium (Reserved-1yr)",
            "estimated_cost": 18.86,
            "llm_model": "gpt-4o-mini",
        }]
        assert insert_ai_recommendations(db_conn, user_id, rows) == 1


class TestUserIsolation:
    def test_users_dont_see_each_other(self, db_conn):
        uid1 = ensure_user(db_conn, "111")
        uid2 = ensure_user(db_conn, "222")
        insert_daily_costs(db_conn, uid1, [{"date": "2024-01-01", "total_cost": 10.0}])
        insert_daily_costs(db_conn, uid2, [{"date": "2024-01-01", "total_cost": 99.0}])

        r1 = get_daily_costs(db_conn, uid1)
        r2 = get_daily_costs(db_conn, uid2)
        assert len(r1) == 1
        assert r1[0]["total_cost"] == 10.0
        assert len(r2) == 1
        assert r2[0]["total_cost"] == 99.0
