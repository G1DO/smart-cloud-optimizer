# Data Schemas

All data is stored in a single SQLite database (`data/cloud_optimizer.db`) managed by `storage/db.py`. Every table is keyed by `user_id` for multi-tenant isolation (except `instance_pricing` which is global reference data).

Insert/query functions follow the pattern `storage.insert_<table>(conn, user_id, rows)` / `storage.get_<table>(conn, user_id, ...)`. Functions do not commit — the caller commits after batching inserts.

---

## Admin Tables (2)

### `users`

| Column | Type | Description |
| --- | --- | --- |
| `user_id` | TEXT PK | Unique user identifier |
| `email` | TEXT UNIQUE | User email |
| `password_hash` | TEXT | Hashed password |
| `profile_name` | TEXT | Display name |
| `user_type` | TEXT | `new`, `connected`, `active`, `inactive` |
| `avg_monthly_spend` | REAL | Average monthly AWS spend |
| `num_services` | INTEGER | Number of AWS services used |
| `created_at` | TEXT | Account creation timestamp |
| `last_login_at` | TEXT | Last login timestamp |

### `aws_connections`

UNIQUE constraint on `(user_id, aws_account_id)`.

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER PK AUTOINCREMENT | Connection ID |
| `user_id` | TEXT FK->users | User reference |
| `connection_name` | TEXT | Display name (e.g., "Production") |
| `aws_account_id` | TEXT NOT NULL | AWS account ID |
| `iam_role_arn` | TEXT NOT NULL | IAM role ARN for cross-account access |
| `external_id` | TEXT | STS external ID |
| `aws_region` | TEXT | Default region (default `us-east-1`) |
| `access_verified` | INTEGER | 0/1 flag (default 0) |
| `last_sync_at` | TEXT | Last successful data sync |
| `sync_status` | TEXT | `never`, `success`, `failed`, `in_progress` |
| `error_message` | TEXT | Last error message |
| `connected_at` | TEXT | Connection timestamp (auto-set) |

---

## Cost Tables (3)

### `daily_costs`

One row per user per day. PK: `(date, user_id)`.

| Column | Type | Description |
| --- | --- | --- |
| `date` | TEXT | `YYYY-MM-DD` |
| `user_id` | TEXT FK→users | User reference |
| `total_cost` | REAL | Total unblended cost in USD |

### `service_costs`

One row per user per day per service. PK: `(date, user_id, service)`.

| Column | Type | Description |
| --- | --- | --- |
| `date` | TEXT | `YYYY-MM-DD` |
| `user_id` | TEXT FK→users | User reference |
| `service` | TEXT | Short service name (`EC2`, `RDS`, `S3`, etc.) |
| `daily_cost` | REAL | Cost for that service on that day |

### `service_region_costs`

One row per user per day per service per region. PK: `(date, user_id, service, region)`.

| Column | Type | Description |
| --- | --- | --- |
| `date` | TEXT | `YYYY-MM-DD` |
| `user_id` | TEXT FK→users | User reference |
| `service` | TEXT | Short service name |
| `region` | TEXT | AWS region |
| `daily_cost` | REAL | Cost for that service+region |

---

## Inventory Tables (10)

### `ec2_instances`

PK: `instance_id`.

| Column | Type | Description |
| --- | --- | --- |
| `instance_id` | TEXT PK | EC2 instance ID |
| `user_id` | TEXT FK→users | User reference |
| `instance_type` | TEXT | e.g. `t3.medium`, `m5.xlarge` |
| `vcpus` | INTEGER | vCPU count |
| `memory_gb` | REAL | Memory in GB |
| `state` | TEXT | `running`, `stopped`, `terminated` |
| `launch_date` | TEXT | Launch date |
| `region` | TEXT | AWS region |
| `availability_zone` | TEXT | AZ |
| `pricing_model` | TEXT | `on-demand`, `reserved-1yr`, `reserved-3yr`, `spot` |
| `monthly_cost` | REAL | Estimated monthly cost |
| `private_ip` | TEXT | Private IPv4 |
| `public_ip` | TEXT | Public IPv4 |
| `vpc_id` | TEXT | VPC identifier |
| `subnet_id` | TEXT | Subnet identifier |
| `ami_id` | TEXT | AMI used to launch |
| `tags` | TEXT | JSON dict of tags |

### `rds_instances`

PK: `db_instance_id`.

| Column | Type | Description |
| --- | --- | --- |
| `db_instance_id` | TEXT PK | RDS instance identifier |
| `user_id` | TEXT FK→users | User reference |
| `db_instance_class` | TEXT | e.g. `db.r5.large` |
| `engine` | TEXT | `postgres`, `mysql`, etc. |
| `engine_version` | TEXT | Engine version |
| `storage_gb` | INTEGER | Provisioned storage |
| `storage_type` | TEXT | `gp2`, `gp3`, `io1` |
| `multi_az` | INTEGER | 0/1 flag |
| `pricing_model` | TEXT | `on-demand`, `reserved-1yr`, `reserved-3yr` |
| `monthly_cost` | REAL | Estimated monthly cost |
| `endpoint` | TEXT | DNS endpoint |
| `port` | INTEGER | Connection port |
| `backup_retention_period` | INTEGER | Days of retention |
| `deletion_protection` | INTEGER | 0/1 flag |

### `elasticache_nodes`

PK: `cache_cluster_id`.

| Column | Type | Description |
| --- | --- | --- |
| `cache_cluster_id` | TEXT PK | Cluster identifier |
| `user_id` | TEXT FK→users | User reference |
| `cache_node_type` | TEXT | e.g. `cache.t3.micro` |
| `engine` | TEXT | `redis` or `memcached` |
| `engine_version` | TEXT | Engine version |
| `num_cache_nodes` | INTEGER | Node count |
| `pricing_model` | TEXT | `on-demand`, `reserved-1yr`, `reserved-3yr` |
| `monthly_cost` | REAL | Estimated monthly cost |

### `ecs_services`

PK: `service_name`.

| Column | Type | Description |
| --- | --- | --- |
| `service_name` | TEXT PK | ECS service name |
| `user_id` | TEXT FK→users | User reference |
| `cluster_name` | TEXT | ECS cluster |
| `launch_type` | TEXT | `FARGATE` or `EC2` |
| `desired_count` | INTEGER | Desired task count |
| `cpu` | INTEGER | CPU units |
| `memory_mb` | INTEGER | Memory in MB |
| `monthly_cost` | REAL | Estimated monthly cost |

### `lambda_functions`

PK: `function_name`.

| Column | Type | Description |
| --- | --- | --- |
| `function_name` | TEXT PK | Function name |
| `user_id` | TEXT FK→users | User reference |
| `runtime` | TEXT | e.g. `python3.12` |
| `memory_mb` | INTEGER | Allocated memory |
| `timeout_sec` | INTEGER | Timeout in seconds |
| `avg_daily_invocations` | INTEGER | Average daily calls |
| `avg_duration_ms` | REAL | Average duration |
| `monthly_cost` | REAL | Estimated monthly cost |
| `code_size` | INTEGER | Deployment package bytes |
| `handler` | TEXT | Handler path |
| `last_modified` | TEXT | Last modified date |

### `ebs_volumes`

PK: `volume_id`.

| Column | Type | Description |
| --- | --- | --- |
| `volume_id` | TEXT PK | EBS volume ID |
| `user_id` | TEXT FK→users | User reference |
| `volume_type` | TEXT | `gp2`, `gp3`, `io2`, `st1` |
| `size_gb` | INTEGER | Volume size |
| `iops` | INTEGER | Provisioned IOPS |
| `throughput_mbps` | INTEGER | Provisioned throughput |
| `attached_instance_id` | TEXT | Attached EC2 instance |
| `state` | TEXT | `in-use` or `available` |
| `monthly_cost` | REAL | Estimated monthly cost |
| `encrypted` | INTEGER | 0/1 flag |
| `create_time` | TEXT | Creation timestamp |

### `s3_buckets`

PK: `bucket_name`.

| Column | Type | Description |
| --- | --- | --- |
| `bucket_name` | TEXT PK | Bucket name |
| `user_id` | TEXT FK→users | User reference |
| `storage_class` | TEXT | `STANDARD`, `INTELLIGENT_TIERING`, etc. |
| `size_gb` | REAL | Total size |
| `num_objects` | INTEGER | Object count |
| `avg_daily_get_requests` | INTEGER | Average daily GETs |
| `avg_daily_put_requests` | INTEGER | Average daily PUTs |
| `monthly_cost` | REAL | Estimated monthly cost |
| `region` | TEXT | AWS region |
| `versioning` | TEXT | Versioning status |
| `encryption` | TEXT | Encryption config |

### `dynamodb_tables`

PK: `table_name`.

| Column | Type | Description |
| --- | --- | --- |
| `table_name` | TEXT PK | Table name |
| `user_id` | TEXT FK→users | User reference |
| `capacity_mode` | TEXT | `PROVISIONED` or `ON_DEMAND` |
| `provisioned_rcu` | INTEGER | Provisioned read capacity units |
| `provisioned_wcu` | INTEGER | Provisioned write capacity units |
| `storage_gb` | REAL | Storage size |
| `item_count` | INTEGER | Number of items |
| `monthly_cost` | REAL | Estimated monthly cost |

### `nat_gateways`

PK: `nat_gateway_id`.

| Column | Type | Description |
| --- | --- | --- |
| `nat_gateway_id` | TEXT PK | NAT Gateway ID |
| `user_id` | TEXT FK→users | User reference |
| `vpc_id` | TEXT | VPC identifier |
| `subnet_id` | TEXT | Subnet identifier |
| `state` | TEXT | Gateway state |
| `monthly_hours` | REAL | Hours per month (default 730) |
| `monthly_data_processed_gb` | REAL | Data processed in GB |
| `monthly_cost` | REAL | Estimated monthly cost |

### `elb_instances`

PK: `elb_arn`.

| Column | Type | Description |
| --- | --- | --- |
| `elb_arn` | TEXT PK | Load balancer ARN |
| `user_id` | TEXT FK→users | User reference |
| `elb_name` | TEXT | Display name |
| `elb_type` | TEXT | `ALB`, `NLB`, `CLB` |
| `scheme` | TEXT | `internet-facing` or `internal` |
| `target_count` | INTEGER | Total target count |
| `healthy_target_count` | INTEGER | Healthy targets |
| `avg_daily_requests` | INTEGER | Average daily requests |
| `monthly_cost` | REAL | Estimated monthly cost |
| `dns_name` | TEXT | DNS endpoint |
| `vpc_id` | TEXT | VPC identifier |
| `state` | TEXT | Load balancer state |
| `created_time` | TEXT | Creation timestamp |

---

## Metrics Tables (10)

All metrics tables share this pattern: PK is `(timestamp, user_id, resource_id)`. Indexed on `user_id` and `timestamp`.

### `ec2_metrics`

| Column | Type | Description |
| --- | --- | --- |
| `timestamp` | TEXT | ISO 8601 timestamp |
| `user_id` | TEXT FK→users | User reference |
| `instance_id` | TEXT | EC2 instance ID |
| `cpu_utilization` | REAL | Average CPU % |
| `cpu_max` | REAL | Maximum CPU % |
| `memory_utilization` | REAL | Memory % (synthetic only) |
| `network_in_kbps` | REAL | Network in (KB/s) |
| `network_out_kbps` | REAL | Network out (KB/s) |
| `disk_read_kbps` | REAL | Disk read (KB/s) |
| `disk_write_kbps` | REAL | Disk write (KB/s) |
| `disk_read_ops` | REAL | Disk read operations |
| `disk_write_ops` | REAL | Disk write operations |

### `rds_metrics`

| Column | Type | Description |
| --- | --- | --- |
| `timestamp` | TEXT | ISO 8601 timestamp |
| `user_id` | TEXT FK→users | User reference |
| `db_instance_id` | TEXT | RDS instance identifier |
| `cpu_utilization` | REAL | Average CPU % |
| `memory_utilization` | REAL | Memory % |
| `read_iops` | REAL | Read IOPS |
| `write_iops` | REAL | Write IOPS |
| `connections` | INTEGER | Active connections |
| `free_storage_gb` | REAL | Free storage in GB |

### `elasticache_metrics`

| Column | Type | Description |
| --- | --- | --- |
| `timestamp` | TEXT | ISO 8601 timestamp |
| `user_id` | TEXT FK→users | User reference |
| `cache_cluster_id` | TEXT | Cluster identifier |
| `cpu_utilization` | REAL | CPU % |
| `memory_utilization` | REAL | Memory % |
| `curr_connections` | INTEGER | Current connections |
| `cache_hits` | INTEGER | Cache hit count |
| `cache_misses` | INTEGER | Cache miss count |
| `evictions` | INTEGER | Eviction count |

### `ecs_metrics`

| Column | Type | Description |
| --- | --- | --- |
| `timestamp` | TEXT | ISO 8601 timestamp |
| `user_id` | TEXT FK→users | User reference |
| `service_name` | TEXT | ECS service name |
| `cluster_name` | TEXT | ECS cluster name |
| `cpu_utilization` | REAL | CPU % |
| `memory_utilization` | REAL | Memory % |
| `running_task_count` | INTEGER | Running tasks |
| `desired_task_count` | INTEGER | Desired tasks |

### `lambda_metrics`

| Column | Type | Description |
| --- | --- | --- |
| `date` | TEXT | `YYYY-MM-DD` |
| `user_id` | TEXT FK→users | User reference |
| `function_name` | TEXT | Function name |
| `invocations` | INTEGER | Daily invocation count |
| `avg_duration_ms` | REAL | Average duration |
| `max_duration_ms` | REAL | Maximum duration |
| `errors` | INTEGER | Error count |
| `throttles` | INTEGER | Throttle count |
| `avg_memory_used_mb` | REAL | Average memory used |
| `memory_allocated_mb` | INTEGER | Memory allocated |

### `ebs_metrics`

| Column | Type | Description |
| --- | --- | --- |
| `timestamp` | TEXT | ISO 8601 timestamp |
| `user_id` | TEXT FK→users | User reference |
| `volume_id` | TEXT | EBS volume ID |
| `read_ops` | REAL | Read operations |
| `write_ops` | REAL | Write operations |
| `read_bytes` | REAL | Read bytes |
| `write_bytes` | REAL | Write bytes |
| `idle_time_seconds` | REAL | Idle time |

### `s3_metrics`

| Column | Type | Description |
| --- | --- | --- |
| `timestamp` | TEXT | ISO 8601 timestamp |
| `user_id` | TEXT FK→users | User reference |
| `bucket_name` | TEXT | Bucket name |
| `bucket_size_bytes` | REAL | Total bucket size |
| `number_of_objects` | INTEGER | Object count |

### `dynamodb_metrics`

| Column | Type | Description |
| --- | --- | --- |
| `timestamp` | TEXT | ISO 8601 timestamp |
| `user_id` | TEXT FK→users | User reference |
| `table_name` | TEXT | DynamoDB table name |
| `consumed_read_units` | REAL | Consumed RCU |
| `consumed_write_units` | REAL | Consumed WCU |
| `provisioned_read_units` | REAL | Provisioned RCU |
| `provisioned_write_units` | REAL | Provisioned WCU |
| `throttled_requests` | INTEGER | Throttled request count |

### `nat_gateway_metrics`

| Column | Type | Description |
| --- | --- | --- |
| `timestamp` | TEXT | ISO 8601 timestamp |
| `user_id` | TEXT FK→users | User reference |
| `nat_gateway_id` | TEXT | NAT Gateway ID |
| `bytes_in` | REAL | Bytes received |
| `bytes_out` | REAL | Bytes sent |
| `packets_in` | INTEGER | Packets received |
| `packets_out` | INTEGER | Packets sent |
| `active_connections` | INTEGER | Active connections |

### `elb_metrics`

| Column | Type | Description |
| --- | --- | --- |
| `timestamp` | TEXT | ISO 8601 timestamp |
| `user_id` | TEXT FK→users | User reference |
| `elb_arn` | TEXT | Load balancer ARN |
| `request_count` | INTEGER | Total requests |
| `active_connections` | INTEGER | Active connections |
| `new_connections` | INTEGER | New connections |
| `processed_bytes` | REAL | Total processed bytes |
| `http_2xx` | INTEGER | 2xx response count |
| `http_3xx` | INTEGER | 3xx response count |
| `http_4xx` | INTEGER | 4xx response count |
| `http_5xx` | INTEGER | 5xx response count |
| `target_response_time_avg` | REAL | Average target response time |

---

## Reference & Analytics Tables (5)

### `instance_pricing`

Global reference table (no `user_id`). PK: `id` (autoincrement). Unique on `(service, instance_type)`.

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER PK | Auto-increment |
| `service` | TEXT | `EC2`, `RDS`, `ElastiCache` |
| `instance_type` | TEXT | e.g. `t3.medium`, `db.r5.large` |
| `vcpus` | INTEGER | vCPU count |
| `memory_gb` | REAL | Memory in GB |
| `category` | TEXT | Instance family category |
| `on_demand_hourly` | REAL | On-demand hourly rate |
| `reserved_1yr_hourly` | REAL | 1-year reserved hourly rate |
| `reserved_3yr_hourly` | REAL | 3-year reserved hourly rate |
| `spot_hourly` | REAL | Spot hourly rate |
| `on_demand_monthly` | REAL | On-demand monthly rate |
| `reserved_1yr_monthly` | REAL | 1-year reserved monthly rate |
| `reserved_3yr_monthly` | REAL | 3-year reserved monthly rate |
| `spot_monthly` | REAL | Spot monthly rate |

### `ai_recommendations`

LLM-generated setup recommendations for new users.

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER PK | Auto-increment |
| `user_id` | TEXT FK→users | User reference |
| `app_type` | TEXT | Application type |
| `expected_users` | INTEGER | Expected daily users |
| `uptime_hours` | INTEGER | Required uptime hours/day |
| `importance` | TEXT | Criticality level |
| `budget_monthly` | REAL | Monthly budget cap |
| `extra_requirements` | TEXT | Additional requirements |
| `prompt_text` | TEXT | Structured prompt sent to LLM |
| `recommended_setup` | TEXT | LLM recommendation |
| `estimated_cost` | REAL | Estimated monthly cost |
| `explanation` | TEXT | Why this setup was chosen |
| `llm_model` | TEXT | Model used (e.g. `gpt-4o-mini`) |
| `llm_response_raw` | TEXT | Raw LLM response |
| `created_at` | TEXT | Timestamp |

### `forecasts`

ML model forecast outputs.

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER PK | Auto-increment |
| `user_id` | TEXT FK→users | User reference |
| `service` | TEXT | Service name (null = total cost) |
| `forecast_date` | TEXT | Forecasted date |
| `predicted_cost` | REAL | Predicted cost |
| `lower_bound` | REAL | Confidence interval lower |
| `upper_bound` | REAL | Confidence interval upper |
| `model_type` | TEXT | `prophet`, `sarimax`, etc. |
| `model_params` | TEXT | JSON model parameters |
| `mae` | REAL | Mean absolute error |
| `mape` | REAL | Mean absolute percentage error |
| `created_at` | TEXT | Timestamp |

### `recommendations`

ML-generated cost optimization recommendations.

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER PK | Auto-increment |
| `user_id` | TEXT FK→users | User reference |
| `service` | TEXT | Service name |
| `resource_id` | TEXT | Resource identifier |
| `recommendation_type` | TEXT | `rightsize`, `pricing_plan_switch`, `storage_class_switch`, `memory_resize`, `volume_type_upgrade`, `delete_unused`, `capacity_mode_switch`, `replace_with_endpoint`, `delete_idle` |
| `current_config` | TEXT | Current resource configuration |
| `recommended_config` | TEXT | Recommended configuration |
| `current_monthly_cost` | REAL | Current cost |
| `estimated_monthly_cost` | REAL | Estimated cost after change |
| `monthly_savings` | REAL | Dollar savings |
| `savings_percent` | REAL | Percentage savings |
| `confidence` | TEXT | `high`, `medium`, `low` |
| `reasoning` | TEXT | Why this recommendation |
| `created_at` | TEXT | Timestamp |

### `anomalies`

Detected cost anomalies.

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER PK | Auto-increment |
| `user_id` | TEXT FK→users | User reference |
| `service` | TEXT | Service name (null = total) |
| `anomaly_date` | TEXT | Date of anomaly |
| `expected_cost` | REAL | Expected cost |
| `actual_cost` | REAL | Actual cost |
| `deviation_percent` | REAL | Deviation from expected |
| `severity` | TEXT | `info`, `warning`, `critical` |
| `description` | TEXT | Human-readable description |
| `created_at` | TEXT | Timestamp |
