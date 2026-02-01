# Data Schemas

Every CSV file produced by both pipelines (real AWS collection and synthetic generation). Column names are identical between the two — downstream modules don't care which pipeline created the data.

---

## Cost Data

### `daily_costs.csv`

One row per account per day.

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID or `SYNTHETIC-001` |
| `date` | string | `YYYY-MM-DD` |
| `cost_amount` | float | Total unblended cost in USD |
| `currency` | string | Always `USD` |

### `service_costs.csv`

One row per account per day per AWS service.

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID |
| `date` | string | `YYYY-MM-DD` |
| `service_name` | string | e.g. `Amazon EC2`, `Amazon S3`, `AWS Lambda` |
| `cost_amount` | float | Cost for that service on that day |
| `currency` | string | Always `USD` |

### `usage_type_cost_consolidated.csv` (real pipeline only)

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID |
| `date` | string | `YYYY-MM-DD` |
| `usage_type` | string | AWS usage type key (e.g. `USW2-BoxUsage:t3.medium`) |
| `cost_amount` | float | Cost for that usage type |
| `currency` | string | Always `USD` |

### `anomalies_consolidated.csv` (real pipeline only)

| Column | Type | Description |
| --- | --- | --- |
| `anomaly_id` | string | AWS anomaly ID |
| `start_date` | string | `YYYY-MM-DD` |
| `end_date` | string | `YYYY-MM-DD` |
| `expected_spend` | float | Expected cost in USD |
| `actual_spend` | float | Actual cost in USD |
| `total_impact` | float | Dollar impact |
| `service` | string | Affected AWS service |

---

## Inventory Data

### `ec2_instances.csv`

One row per EC2 instance.

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID |
| `region` | string | e.g. `us-east-1` |
| `instance_id` | string | e.g. `i-0abc123def456` |
| `instance_type` | string | e.g. `t3.medium`, `m5.xlarge` |
| `state` | string | `running`, `stopped`, `terminated` |
| `availability_zone` | string | e.g. `us-east-1a` |
| `launch_time` | string | ISO 8601 timestamp |
| `private_ip` | string | Private IPv4 address |
| `public_ip` | string | Public IPv4 (empty if none) |
| `vpc_id` | string | VPC identifier |
| `subnet_id` | string | Subnet identifier |
| `ami_id` | string | AMI used to launch |
| `tenancy` | string | `default`, `dedicated`, `host` |
| `hypervisor` | string | `xen` or `nitro` |
| `architecture` | string | `x86_64` or `arm64` |
| `monitoring` | string | `enabled` or `disabled` |
| `cpu_cores` | int | vCPU count |
| `threads_per_core` | int | Threads per physical core |
| `security_groups` | string | JSON list of SG IDs |
| `ebs_volumes` | string | JSON list of attached volume IDs |
| `network_interfaces` | string | JSON list of ENI IDs |
| `tags` | string | JSON dict of instance tags |

### `rds_instances.csv`

One row per RDS instance.

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID |
| `region` | string | AWS region |
| `db_instance_id` | string | RDS instance identifier |
| `engine` | string | `postgres`, `mysql`, etc. |
| `engine_version` | string | e.g. `15.4` |
| `db_instance_class` | string | e.g. `db.r5.large` |
| `multi_az` | bool | Multi-AZ deployment |
| `allocated_storage_gb` | int | Provisioned storage in GB |
| `storage_type` | string | `gp2`, `gp3`, `io1` |
| `iops` | int | Provisioned IOPS (0 if N/A) |
| `status` | string | `available`, `stopped`, etc. |
| `endpoint` | string | DNS endpoint |
| `port` | int | Connection port |
| `publicly_accessible` | bool | Public access flag |
| `max_allocated_storage` | int | Autoscaling max GB |
| `backup_retention_period` | int | Days of backup retention |
| `auto_minor_version_upgrade` | bool | Auto-upgrade flag |
| `deletion_protection` | bool | Deletion protection flag |
| `instance_create_time` | string | ISO 8601 timestamp |
| `tags` | string | JSON dict of tags |

### `s3_buckets.csv`

One row per S3 bucket.

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID |
| `bucket_name` | string | Bucket name |
| `region` | string | AWS region |
| `creation_date` | string | ISO 8601 timestamp |
| `versioning` | string | `Enabled`, `Suspended`, or empty |
| `default_encryption` | string | Encryption algorithm |
| `public_access_block` | string | JSON public access config |

### `lambda_functions.csv`

One row per Lambda function.

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID |
| `region` | string | AWS region |
| `function_name` | string | Function name |
| `function_arn` | string | Full ARN |
| `runtime` | string | e.g. `python3.12`, `nodejs20.x` |
| `memory_size` | int | MB allocated |
| `timeout` | int | Timeout in seconds |
| `handler` | string | Handler path |
| `last_modified` | string | ISO 8601 timestamp |
| `code_size` | int | Deployment package bytes |
| `description` | string | Function description |
| `vpc_subnet_ids` | string | Comma-separated subnet IDs |
| `vpc_security_group_ids` | string | Comma-separated SG IDs |
| `tags` | string | JSON dict of tags |

### `ebs_volumes.csv`

One row per EBS volume.

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID |
| `region` | string | AWS region |
| `volume_id` | string | e.g. `vol-0abc123` |
| `size_gb` | int | Volume size in GB |
| `volume_type` | string | `gp2`, `gp3`, `io2`, `st1` |
| `iops` | int | Provisioned IOPS |
| `throughput` | int | Provisioned throughput MB/s |
| `encrypted` | bool | Encryption flag |
| `state` | string | `in-use`, `available` |
| `availability_zone` | string | AZ |
| `snapshot_id` | string | Source snapshot (empty if none) |
| `create_time` | string | ISO 8601 timestamp |
| `attachments` | string | JSON list of attachment info |
| `tags` | string | JSON dict of tags |

### Real pipeline only: `instances_consolidated.csv`, `volumes_consolidated.csv`, `regions_consolidated.csv`

These are direct dumps from `ec2.describe_instances()`, `ec2.describe_volumes()`, and `ec2.describe_regions()` with columns matching the AWS API response fields.

---

## Metrics Data

### `ec2_metrics.csv`

One row per instance per timestamp (hourly resolution).

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID |
| `region` | string | AWS region |
| `instance_id` | string | EC2 instance ID |
| `timestamp` | string | ISO 8601 timestamp |
| `cpu_avg` | float | Average CPU utilization (%) |
| `cpu_max` | float | Maximum CPU utilization (%) |
| `network_in_avg` | float | Average network bytes in |
| `network_out_avg` | float | Average network bytes out |
| `disk_read_ops_avg` | float | Average disk read operations |
| `disk_write_ops_avg` | float | Average disk write operations |
| `disk_read_bytes_avg` | float | Average disk read bytes |
| `disk_write_bytes_avg` | float | Average disk write bytes |
| `status_check_failed_max` | float | Max status check failures (0 or 1) |
| `memory_used_percent_avg` | float | Memory usage (synthetic only, 0.0 for real) |
| `period_seconds` | int | CloudWatch period (3600 = hourly) |

### `rds_metrics.csv`

One row per RDS instance per timestamp.

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID |
| `region` | string | AWS region |
| `db_instance_id` | string | RDS instance identifier |
| `timestamp` | string | ISO 8601 timestamp |
| `cpu_util_avg` | float | Average CPU utilization (%) |
| `free_storage_avg` | float | Free storage bytes |
| `free_mem_avg` | float | Free memory bytes |
| `db_conns_avg` | float | Active database connections |
| `read_iops_avg` | float | Read IOPS |
| `write_iops_avg` | float | Write IOPS |
| `read_latency_avg` | float | Read latency (seconds) |
| `write_latency_avg` | float | Write latency (seconds) |
| `queue_depth_avg` | float | I/O queue depth |
| `net_rx_avg` | float | Network receive bytes |
| `net_tx_avg` | float | Network transmit bytes |
| `period_seconds` | int | CloudWatch period |

### Real pipeline only: other metrics CSVs

| File | Key columns |
| --- | --- |
| `ebs_metrics_consolidated.csv` | `volume_id`, `timestamp`, `read_bytes_avg`, `write_bytes_avg`, `idle_time_avg`, `consumed_rw_ops_avg` |
| `lambda_metrics_consolidated.csv` | `function_name`, `timestamp`, `invocations_sum`, `duration_avg`, `errors_sum` |
| `s3_metrics_consolidated.csv` | `bucket_name`, `timestamp`, `bucket_size_bytes`, `number_of_objects` |
| `cloudfront_metrics_consolidated.csv` | `distribution_id`, `timestamp`, `requests_sum`, `bytes_downloaded_sum`, `cache_hit_rate_avg`, `error_rate_avg` |
| `nat_metrics_consolidated.csv` | `nat_gateway_id`, `region`, `timestamp`, `bytes_processed_sum`, `active_connections_avg` |
| `alb_metrics_consolidated.csv` | `lb_arn`, `timestamp`, `request_count_sum`, `http_4xx_count_sum`, `http_5xx_count_sum` |
| `nlb_metrics_consolidated.csv` | `lb_arn`, `timestamp`, `processed_bytes_sum`, `new_flow_count_sum` |

---

## Pricing Data

### `instance_pricing.csv`

One row per instance type per pricing model per month.

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | string | AWS account ID |
| `month` | string | `YYYY-MM` |
| `service` | string | `EC2`, `RDS`, `Lambda`, `S3` |
| `pricing_type` | string | `OnDemand`, `Reserved1yr`, `Reserved3yr`, `Spot` |
| `instance_type` | string | e.g. `t3.medium` (or storage class for S3) |
| `region` | string | AWS region |
| `hourly_price_usd` | float | Price per hour (or per GB/request for S3/Lambda) |
| `product_family` | string | `Compute Instance`, `Storage`, `Serverless` |

---

## AI Recommendations (synthetic only)

### `ai_recommendations_sample.csv`

Sample output showing what the AI module would produce.

| Column | Type | Description |
| --- | --- | --- |
| `id` | int | Recommendation ID |
| `app_type` | string | `web`, `api`, `batch`, etc. |
| `daily_users` | int | Expected daily users |
| `uptime_hours` | int | Required uptime hours/day |
| `importance` | string | `critical`, `high`, `medium`, `low` |
| `budget_usd` | float | Monthly budget cap |
| `region` | string | Preferred AWS region |
| `recommended_instance` | string | Suggested instance type |
| `recommended_pricing` | string | Suggested pricing model |
| `estimated_cost_usd` | float | Estimated monthly cost |
| `explanation` | string | Human-readable explanation |
| `created_at` | string | ISO 8601 timestamp |
