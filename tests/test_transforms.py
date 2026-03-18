"""Tests for aws_collector.transforms — data transformation helpers."""
import json
from datetime import datetime

from aws_collector.transforms import (
    flatten_cw_metrics,
    transform_daily_costs,
    transform_service_costs,
    transform_ec2_instances,
    transform_ebs_volumes,
    transform_rds_instances,
    transform_lambda_functions,
    transform_nat_gateways,
    transform_lb_inventory,
    transform_elasticache_nodes,
    transform_ecs_services,
    transform_dynamodb_tables,
    transform_pricing,
)


# ======================================================================
# flatten_cw_metrics
# ======================================================================


class TestFlattenCWMetrics:
    def test_basic_flatten(self):
        ts = datetime(2024, 3, 1, 12, 0, 0)
        data = {
            "instance_id": "i-abc123",
            "metrics": {
                "CPUUtilization": [
                    {"Timestamp": ts, "Average": 42.5},
                ],
            },
        }
        metric_map = {"CPUUtilization_average": "cpu_utilization"}
        rows = flatten_cw_metrics(data, "instance_id", metric_map)

        assert len(rows) == 1
        assert rows[0]["instance_id"] == "i-abc123"
        assert rows[0]["cpu_utilization"] == 42.5

    def test_multiple_metrics_same_timestamp(self):
        ts = datetime(2024, 3, 1, 12, 0, 0)
        data = {
            "instance_id": "i-abc123",
            "metrics": {
                "CPUUtilization": [{"Timestamp": ts, "Average": 50.0}],
                "NetworkIn": [{"Timestamp": ts, "Average": 1024.0}],
            },
        }
        metric_map = {
            "CPUUtilization_average": "cpu_utilization",
            "NetworkIn_average": "network_in",
        }
        rows = flatten_cw_metrics(data, "instance_id", metric_map)

        assert len(rows) == 1
        assert rows[0]["cpu_utilization"] == 50.0
        assert rows[0]["network_in"] == 1024.0

    def test_multiple_timestamps(self):
        ts1 = datetime(2024, 3, 1, 12, 0, 0)
        ts2 = datetime(2024, 3, 1, 13, 0, 0)
        data = {
            "instance_id": "i-abc123",
            "metrics": {
                "CPUUtilization": [
                    {"Timestamp": ts1, "Average": 30.0},
                    {"Timestamp": ts2, "Average": 60.0},
                ],
            },
        }
        metric_map = {"CPUUtilization_average": "cpu_utilization"}
        rows = flatten_cw_metrics(data, "instance_id", metric_map)

        assert len(rows) == 2
        assert rows[0]["cpu_utilization"] == 30.0
        assert rows[1]["cpu_utilization"] == 60.0

    def test_maximum_statistic(self):
        ts = datetime(2024, 3, 1, 12, 0, 0)
        data = {
            "instance_id": "i-abc123",
            "metrics": {
                "CPUUtilization": [
                    {"Timestamp": ts, "Average": 40.0, "Maximum": 95.0},
                ],
            },
        }
        metric_map = {
            "CPUUtilization_average": "cpu_avg",
            "CPUUtilization_maximum": "cpu_max",
        }
        rows = flatten_cw_metrics(data, "instance_id", metric_map)

        assert rows[0]["cpu_avg"] == 40.0
        assert rows[0]["cpu_max"] == 95.0

    def test_empty_metrics(self):
        data = {"instance_id": "i-abc123", "metrics": {}}
        rows = flatten_cw_metrics(data, "instance_id", {})
        assert rows == []

    def test_missing_resource_id(self):
        ts = datetime(2024, 3, 1, 12, 0, 0)
        data = {
            "metrics": {
                "CPUUtilization": [{"Timestamp": ts, "Average": 10.0}],
            },
        }
        metric_map = {"CPUUtilization_average": "cpu"}
        rows = flatten_cw_metrics(data, "instance_id", metric_map)
        assert rows[0]["instance_id"] == ""

    def test_none_value_becomes_zero(self):
        ts = datetime(2024, 3, 1, 12, 0, 0)
        data = {
            "instance_id": "i-abc123",
            "metrics": {
                "CPUUtilization": [{"Timestamp": ts, "Average": None}],
            },
        }
        metric_map = {"CPUUtilization_average": "cpu"}
        rows = flatten_cw_metrics(data, "instance_id", metric_map)
        assert rows[0]["cpu"] == 0.0

    def test_unmapped_metric_ignored(self):
        ts = datetime(2024, 3, 1, 12, 0, 0)
        data = {
            "instance_id": "i-abc123",
            "metrics": {
                "UnknownMetric": [{"Timestamp": ts, "Average": 99.0}],
            },
        }
        metric_map = {"CPUUtilization_average": "cpu"}
        rows = flatten_cw_metrics(data, "instance_id", metric_map)
        assert len(rows) == 1
        assert "cpu" not in rows[0]

    def test_string_timestamp(self):
        data = {
            "instance_id": "i-abc123",
            "metrics": {
                "CPUUtilization": [{"Timestamp": "2024-03-01T12:00:00", "Average": 5.0}],
            },
        }
        metric_map = {"CPUUtilization_average": "cpu"}
        rows = flatten_cw_metrics(data, "instance_id", metric_map)
        assert len(rows) == 1
        assert rows[0]["timestamp"] == "2024-03-01T12:00:00"


# ======================================================================
# transform_daily_costs
# ======================================================================


class TestTransformDailyCosts:
    def test_basic(self):
        cost_data = {
            "data": [
                {
                    "TimePeriod": {"Start": "2024-03-01"},
                    "Total": {"UnblendedCost": {"Amount": "123.45"}},
                },
            ]
        }
        rows = transform_daily_costs(cost_data)
        assert len(rows) == 1
        assert rows[0]["date"] == "2024-03-01"
        assert rows[0]["total_cost"] == 123.45

    def test_multiple_days(self):
        cost_data = {
            "data": [
                {"TimePeriod": {"Start": "2024-03-01"}, "Total": {"UnblendedCost": {"Amount": "10"}}},
                {"TimePeriod": {"Start": "2024-03-02"}, "Total": {"UnblendedCost": {"Amount": "20"}}},
            ]
        }
        rows = transform_daily_costs(cost_data)
        assert len(rows) == 2
        assert rows[1]["total_cost"] == 20.0

    def test_empty_data(self):
        assert transform_daily_costs({"data": []}) == []
        assert transform_daily_costs({}) == []

    def test_missing_amount_defaults_zero(self):
        cost_data = {
            "data": [
                {"TimePeriod": {"Start": "2024-03-01"}, "Total": {"UnblendedCost": {"Amount": ""}}},
            ]
        }
        rows = transform_daily_costs(cost_data)
        assert rows[0]["total_cost"] == 0.0


# ======================================================================
# transform_service_costs
# ======================================================================


class TestTransformServiceCosts:
    def test_basic(self):
        cost_data = {
            "data": [
                {
                    "TimePeriod": {"Start": "2024-03-01"},
                    "Groups": [
                        {"Keys": ["Amazon Elastic Compute Cloud - Compute"], "Metrics": {"UnblendedCost": {"Amount": "55.0"}}},
                        {"Keys": ["Amazon Simple Storage Service"], "Metrics": {"UnblendedCost": {"Amount": "12.0"}}},
                    ],
                },
            ]
        }
        rows = transform_service_costs(cost_data)
        assert len(rows) == 2
        assert rows[0]["daily_cost"] == 55.0

    def test_empty(self):
        assert transform_service_costs({"data": []}) == []
        assert transform_service_costs({}) == []


# ======================================================================
# transform_ec2_instances
# ======================================================================


class TestTransformEC2Instances:
    def test_basic_instance(self):
        instances = [{
            "instance_id": "i-abc123",
            "instance_type": "t3.micro",
            "state": "running",
            "launch_time": "2024-01-01T00:00:00",
            "region": "us-east-1",
            "availability_zone": "us-east-1a",
        }]
        rows = transform_ec2_instances(instances)
        assert len(rows) == 1
        assert rows[0]["instance_id"] == "i-abc123"
        assert rows[0]["instance_type"] == "t3.micro"
        assert rows[0]["state"] == "running"

    def test_tags_dict_serialized_to_json(self):
        instances = [{
            "instance_id": "i-abc123",
            "tags": {"Name": "web-server", "Env": "prod"},
        }]
        rows = transform_ec2_instances(instances)
        assert json.loads(rows[0]["tags"]) == {"Name": "web-server", "Env": "prod"}

    def test_tags_string_preserved(self):
        instances = [{
            "instance_id": "i-abc123",
            "tags": '{"Name": "already-json"}',
        }]
        rows = transform_ec2_instances(instances)
        assert rows[0]["tags"] == '{"Name": "already-json"}'

    def test_missing_optional_fields_default(self):
        instances = [{"instance_id": "i-abc123"}]
        rows = transform_ec2_instances(instances)
        assert rows[0]["instance_type"] == ""
        assert rows[0]["state"] == "running"
        assert rows[0]["region"] == "us-east-1"
        assert rows[0]["private_ip"] is None


# ======================================================================
# transform_ebs_volumes
# ======================================================================


class TestTransformEBSVolumes:
    def test_basic_volume(self):
        volumes = [{
            "volume_id": "vol-abc123",
            "volume_type": "gp3",
            "size_gb": 100,
            "iops": 3000,
        }]
        rows = transform_ebs_volumes(volumes)
        assert rows[0]["volume_id"] == "vol-abc123"
        assert rows[0]["size_gb"] == 100

    def test_defaults(self):
        volumes = [{"volume_id": "vol-abc123"}]
        rows = transform_ebs_volumes(volumes)
        assert rows[0]["volume_type"] == "gp3"
        assert rows[0]["size_gb"] == 0

    def test_optional_fields_none(self):
        volumes = [{"volume_id": "vol-abc123"}]
        rows = transform_ebs_volumes(volumes)
        assert rows[0]["iops"] is None
        assert rows[0]["throughput_mbps"] is None


# ======================================================================
# transform_rds_instances
# ======================================================================


class TestTransformRDSInstances:
    def test_basic(self):
        db_instances = [{
            "DBInstanceIdentifier": "mydb",
            "DBInstanceClass": "db.t3.medium",
            "Engine": "postgres",
            "EngineVersion": "15.4",
            "AllocatedStorage": 50,
            "StorageType": "gp3",
            "MultiAZ": True,
            "Endpoint": {"Address": "mydb.xxx.rds.amazonaws.com", "Port": 5432},
            "BackupRetentionPeriod": 7,
            "DeletionProtection": True,
        }]
        rows = transform_rds_instances(db_instances)
        assert rows[0]["db_instance_id"] == "mydb"
        assert rows[0]["engine"] == "postgres"
        assert rows[0]["multi_az"] == 1
        assert rows[0]["deletion_protection"] == 1
        assert rows[0]["endpoint"] == "mydb.xxx.rds.amazonaws.com"
        assert rows[0]["port"] == 5432

    def test_defaults(self):
        db_instances = [{"DBInstanceIdentifier": "mydb"}]
        rows = transform_rds_instances(db_instances)
        assert rows[0]["multi_az"] == 0
        assert rows[0]["deletion_protection"] == 0
        assert rows[0]["storage_gb"] == 0


# ======================================================================
# transform_lambda_functions
# ======================================================================


class TestTransformLambdaFunctions:
    def test_basic(self):
        functions = [{
            "FunctionName": "my-func",
            "Runtime": "python3.12",
            "MemorySize": 256,
            "Timeout": 60,
            "CodeSize": 5000,
            "Handler": "index.handler",
            "LastModified": "2024-03-01T00:00:00",
        }]
        rows = transform_lambda_functions(functions)
        assert rows[0]["function_name"] == "my-func"
        assert rows[0]["runtime"] == "python3.12"
        assert rows[0]["memory_mb"] == 256

    def test_defaults(self):
        functions = [{"FunctionName": "f"}]
        rows = transform_lambda_functions(functions)
        assert rows[0]["timeout_sec"] == 30
        assert rows[0]["runtime"] == ""


# ======================================================================
# transform_nat_gateways
# ======================================================================


class TestTransformNATGateways:
    def test_passthrough(self):
        gateways = [{"nat_gateway_id": "nat-abc", "state": "available"}]
        assert transform_nat_gateways(gateways) is gateways


# ======================================================================
# transform_lb_inventory
# ======================================================================


class TestTransformLBInventory:
    def test_type_mapping(self):
        lbs = [
            {"lb_arn": "arn:1", "lb_name": "app-lb", "type": "application"},
            {"lb_arn": "arn:2", "lb_name": "net-lb", "type": "network"},
            {"lb_arn": "arn:3", "lb_name": "cls-lb", "type": "classic"},
        ]
        rows = transform_lb_inventory(lbs)
        assert rows[0]["elb_type"] == "ALB"
        assert rows[1]["elb_type"] == "NLB"
        assert rows[2]["elb_type"] == "CLB"

    def test_defaults(self):
        lbs = [{"lb_arn": "arn:1"}]
        rows = transform_lb_inventory(lbs)
        assert rows[0]["elb_name"] == ""
        assert rows[0]["scheme"] == "internet-facing"
        assert rows[0]["state"] == "active"

    def test_unknown_type_preserved(self):
        lbs = [{"lb_arn": "arn:1", "type": "gateway"}]
        rows = transform_lb_inventory(lbs)
        assert rows[0]["elb_type"] == "gateway"


# ======================================================================
# transform_elasticache_nodes
# ======================================================================


class TestTransformElastiCacheNodes:
    def test_basic(self):
        clusters = [{
            "cache_cluster_id": "my-redis",
            "cache_node_type": "cache.t3.micro",
            "engine": "redis",
            "engine_version": "7.0",
            "num_cache_nodes": 2,
        }]
        rows = transform_elasticache_nodes(clusters)
        assert rows[0]["cache_cluster_id"] == "my-redis"
        assert rows[0]["num_cache_nodes"] == 2

    def test_defaults(self):
        clusters = [{"cache_cluster_id": "c1"}]
        rows = transform_elasticache_nodes(clusters)
        assert rows[0]["num_cache_nodes"] == 1
        assert rows[0]["engine"] == ""


# ======================================================================
# transform_ecs_services
# ======================================================================


class TestTransformECSServices:
    def test_basic(self):
        services = [{
            "service_name": "web",
            "cluster_name": "prod",
            "launch_type": "FARGATE",
            "desired_count": 3,
            "cpu": 512,
            "memory_mb": 1024,
        }]
        rows = transform_ecs_services(services)
        assert rows[0]["service_name"] == "web"
        assert rows[0]["cpu"] == 512

    def test_defaults(self):
        services = [{"service_name": "api"}]
        rows = transform_ecs_services(services)
        assert rows[0]["launch_type"] == "FARGATE"
        assert rows[0]["desired_count"] == 1
        assert rows[0]["cpu"] == 256
        assert rows[0]["memory_mb"] == 512


# ======================================================================
# transform_dynamodb_tables
# ======================================================================


class TestTransformDynamoDBTables:
    def test_basic(self):
        tables = [{
            "table_name": "users",
            "capacity_mode": "ON_DEMAND",
            "storage_gb": 5,
            "item_count": 10000,
        }]
        rows = transform_dynamodb_tables(tables)
        assert rows[0]["table_name"] == "users"
        assert rows[0]["capacity_mode"] == "ON_DEMAND"

    def test_defaults(self):
        tables = [{"table_name": "t1"}]
        rows = transform_dynamodb_tables(tables)
        assert rows[0]["capacity_mode"] == "PROVISIONED"
        assert rows[0]["storage_gb"] == 0
        assert rows[0]["item_count"] == 0


# ======================================================================
# transform_pricing
# ======================================================================


class TestTransformPricing:
    def test_on_demand(self):
        raw = [{
            "service": "EC2",
            "instance_type": "t3.micro",
            "pricing_type": "On-Demand",
            "hourly_price_usd": 0.0104,
        }]
        rows = transform_pricing(raw)
        assert len(rows) == 1
        assert rows[0]["on_demand_hourly"] == 0.0104
        assert abs(rows[0]["on_demand_monthly"] - 0.0104 * 730) < 0.01

    def test_reserved_and_spot_merged(self):
        raw = [
            {"service": "EC2", "instance_type": "m5.large", "pricing_type": "On-Demand", "hourly_price_usd": 0.096},
            {"service": "EC2", "instance_type": "m5.large", "pricing_type": "Reserved-1yr", "price_usd": 0.06},
            {"service": "EC2", "instance_type": "m5.large", "pricing_type": "Reserved-3yr", "price_usd": 0.04},
            {"service": "EC2", "instance_type": "m5.large", "pricing_type": "Spot", "hourly_price_usd": 0.03},
        ]
        rows = transform_pricing(raw)
        assert len(rows) == 1
        r = rows[0]
        assert r["on_demand_hourly"] == 0.096
        assert r["reserved_1yr_hourly"] == 0.06
        assert r["reserved_3yr_hourly"] == 0.04
        assert r["spot_hourly"] == 0.03

    def test_empty_input(self):
        assert transform_pricing([]) == []

    def test_missing_instance_type_skipped(self):
        raw = [{"service": "EC2", "pricing_type": "On-Demand", "hourly_price_usd": 0.01}]
        assert transform_pricing(raw) == []

    def test_different_services_separate(self):
        raw = [
            {"service": "EC2", "instance_type": "t3.micro", "pricing_type": "On-Demand", "hourly_price_usd": 0.01},
            {"service": "RDS", "instance_type": "db.t3.micro", "pricing_type": "On-Demand", "hourly_price_usd": 0.02},
        ]
        rows = transform_pricing(raw)
        assert len(rows) == 2

    def test_instance_class_fallback(self):
        raw = [{"service": "RDS", "instance_class": "db.t3.micro", "pricing_type": "On-Demand", "hourly_price_usd": 0.02}]
        rows = transform_pricing(raw)
        assert rows[0]["instance_type"] == "db.t3.micro"
