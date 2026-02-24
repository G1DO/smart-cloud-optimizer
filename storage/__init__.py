"""storage — SQLite storage layer for Smart Cloud Optimizer.

Single data gateway: all modules read/write through this package.

Part of the Smart Cloud Optimizer graduation project.
"""
from config import INSTANCE_SPECS, SERVICE_NAME_MAP
from .db import (
    # Connection & schema
    get_connection,
    ensure_schema,
    create_schema,
    ensure_user,
    clear_user_data,
    # Auth & password
    hash_password,
    verify_password,
    register_user,
    authenticate_user,
    get_user_by_id,
    update_user_profile,
    # AWS connection CRUD
    add_aws_connection,
    get_aws_connections,
    delete_aws_connection,
    update_aws_connection_status,
    # Write API — cost
    insert_daily_costs,
    insert_service_costs,
    insert_service_region_costs,
    # Write API — inventory
    insert_ec2_instances,
    insert_rds_instances,
    insert_elasticache_nodes,
    insert_ecs_services,
    insert_lambda_functions,
    insert_ebs_volumes,
    insert_s3_buckets,
    insert_dynamodb_tables,
    insert_nat_gateways,
    insert_elb_instances,
    # Write API — metrics
    insert_ec2_metrics,
    insert_rds_metrics,
    insert_elasticache_metrics,
    insert_ecs_metrics,
    insert_lambda_metrics,
    insert_ebs_metrics,
    insert_s3_metrics,
    insert_dynamodb_metrics,
    insert_nat_gateway_metrics,
    insert_elb_metrics,
    # Write API — pricing
    insert_instance_pricing,
    # Write API — analytics results
    insert_forecasts,
    insert_recommendations,
    insert_anomalies,
    insert_ai_recommendations,
    # Read API — cost
    get_daily_costs,
    get_service_costs,
    get_service_region_costs,
    # Read API — inventory
    get_ec2_instances,
    get_rds_instances,
    get_elasticache_nodes,
    get_ecs_services,
    get_lambda_functions,
    get_ebs_volumes,
    get_s3_buckets,
    get_dynamodb_tables,
    get_nat_gateways,
    get_elb_instances,
    # Read API — metrics
    get_ec2_metrics,
    get_rds_metrics,
    get_elasticache_metrics,
    get_ecs_metrics,
    get_lambda_metrics,
    get_ebs_metrics,
    get_s3_metrics,
    get_dynamodb_metrics,
    get_nat_gateway_metrics,
    get_elb_metrics,
    # Read API — pricing
    get_instance_pricing,
    # Read API — analytics results
    get_forecasts,
    get_recommendations,
    get_anomalies,
    get_ai_recommendations,
)

__all__ = [
    "get_connection", "ensure_schema", "create_schema", "ensure_user", "clear_user_data",
    "hash_password", "verify_password",
    "register_user", "authenticate_user", "get_user_by_id", "update_user_profile",
    "add_aws_connection", "get_aws_connections", "delete_aws_connection",
    "update_aws_connection_status",
    "INSTANCE_SPECS", "SERVICE_NAME_MAP",
    # insert_*
    "insert_daily_costs", "insert_service_costs", "insert_service_region_costs",
    "insert_ec2_instances", "insert_ec2_metrics",
    "insert_rds_instances", "insert_rds_metrics",
    "insert_elasticache_nodes", "insert_elasticache_metrics",
    "insert_ecs_services", "insert_ecs_metrics",
    "insert_lambda_functions", "insert_lambda_metrics",
    "insert_ebs_volumes", "insert_ebs_metrics",
    "insert_s3_buckets", "insert_s3_metrics",
    "insert_dynamodb_tables", "insert_dynamodb_metrics",
    "insert_nat_gateways", "insert_nat_gateway_metrics",
    "insert_elb_instances", "insert_elb_metrics",
    "insert_instance_pricing",
    "insert_forecasts", "insert_recommendations",
    "insert_anomalies", "insert_ai_recommendations",
    # get_*
    "get_daily_costs", "get_service_costs", "get_service_region_costs",
    "get_ec2_instances", "get_ec2_metrics",
    "get_rds_instances", "get_rds_metrics",
    "get_elasticache_nodes", "get_elasticache_metrics",
    "get_ecs_services", "get_ecs_metrics",
    "get_lambda_functions", "get_lambda_metrics",
    "get_ebs_volumes", "get_ebs_metrics",
    "get_s3_buckets", "get_s3_metrics",
    "get_dynamodb_tables", "get_dynamodb_metrics",
    "get_nat_gateways", "get_nat_gateway_metrics",
    "get_elb_instances", "get_elb_metrics",
    "get_instance_pricing",
    "get_forecasts", "get_recommendations",
    "get_anomalies", "get_ai_recommendations",
]
