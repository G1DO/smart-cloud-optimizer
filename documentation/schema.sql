-- ============================================================================
-- SMART CLOUD OPTIMIZER — Complete Database Schema
-- ============================================================================
-- Database: SQLite (cloud_optimizer.db)
-- Services: EC2, RDS, ElastiCache, ECS/Fargate, S3, Lambda, EBS, DynamoDB,
--           NAT Gateway, ELB/ALB
-- Tables:   30 total (2 core + 3 cost + 11 metrics + 10 inventory + 1 pricing + 4 output)
-- NOTE:     The authoritative schema lives in storage/db.py (_SCHEMA_DDL).
--           This file is a human-readable reference. If they diverge, db.py wins.
-- ============================================================================

PRAGMA journal_mode = WAL;          -- Better concurrent read performance
PRAGMA foreign_keys = ON;           -- Enforce referential integrity

-- ============================================================================
-- 0. USERS TABLE — Central entity, everything references this
-- ============================================================================
-- WHY: Every metric, cost, and inventory row belongs to a user.
--      This is the single source of truth for user profiles.
--
-- ONBOARDING FLOW:
--   1. User signs up → row created with user_type='new' (no AWS data yet)
--   2. AI module runs (questions → prompt → recommendation)
--   3. If user connects AWS → user_type changes to 'connected'
--   4. System pulls data → user_type changes to 'active'
--   5. ML optimization runs on their real data

CREATE TABLE IF NOT EXISTS users (
    user_id           TEXT PRIMARY KEY,                -- UUID or auto-generated
    email             TEXT    NOT NULL UNIQUE,
    password_hash     TEXT    NOT NULL,                -- bcrypt/argon2 hash, NEVER plaintext
    profile_name      TEXT,                            -- 'My Startup', 'Personal Blog'
    user_type         TEXT    NOT NULL DEFAULT 'new',  -- Drives which module runs
    avg_monthly_spend REAL,                            -- NULL until first sync
    num_services      INTEGER,                         -- NULL until first sync
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login_at     TEXT,
    CHECK (user_type IN ('new','connected','active','inactive'))
    -- new        = just signed up, no AWS linked (→ AI module)
    -- connected  = AWS role linked, not synced yet
    -- active     = has synced data (→ ML module)
    -- inactive   = no sync in 30+ days
);

-- ============================================================================
-- 0b. AWS_CONNECTIONS — How the system connects to each user's AWS account
-- ============================================================================
-- WHY: When a user clicks "Connect AWS Account", they create an IAM Role
--      in their own AWS account that gives OUR system read-only access.
--      This table stores the connection config. NEVER secret keys.
--
-- HOW IT WORKS (Cross-Account IAM Role):
--   1. User goes to their AWS Console
--   2. Creates IAM Role with our trust policy + read-only permissions
--      (or runs the CloudFormation template we provide)
--   3. Pastes the Role ARN into our app
--   4. Our system calls sts:AssumeRole to get temporary credentials
--   5. Uses temp credentials to call Cost Explorer, CloudWatch, etc.
--
-- SECURITY:
--   - We NEVER see or store the user's AWS password or root keys
--   - The IAM Role has read-only permissions only
--   - Temp credentials from AssumeRole expire in 1 hour
--   - User can revoke access anytime by deleting the role

CREATE TABLE IF NOT EXISTS aws_connections (
    user_id           TEXT PRIMARY KEY,
    aws_account_id    TEXT    NOT NULL,                 -- '123456789012' (from the ARN)
    iam_role_arn      TEXT    NOT NULL,                 -- 'arn:aws:iam::123456789012:role/CloudOptimizerReadOnly'
    external_id       TEXT,                             -- Extra security token for AssumeRole
    aws_region        TEXT    NOT NULL DEFAULT 'us-east-1',
    access_verified   INTEGER NOT NULL DEFAULT 0,       -- 0=not tested, 1=verified working
    last_sync_at      TEXT,                             -- Last successful data pull
    sync_status       TEXT    NOT NULL DEFAULT 'never', -- 'never','success','failed','in_progress'
    error_message     TEXT,                             -- Last error if sync_status='failed'
    connected_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (sync_status IN ('never','success','failed','in_progress'))
);

-- ============================================================================
-- 1. COST TABLES — Time-series forecasting training data
-- ============================================================================

-- 1a. DAILY_COSTS — One row per user per day (total across all services)
-- WHY: This is the PRIMARY forecasting target. Any model fits on (date, cost).
--      365 days × 8 users = 2,920 rows.

CREATE TABLE IF NOT EXISTS daily_costs (
    date              TEXT    NOT NULL,                -- 'YYYY-MM-DD'
    user_id           TEXT    NOT NULL,
    total_cost        REAL    NOT NULL,                -- Sum of all services that day
    PRIMARY KEY (date, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_daily_costs_user    ON daily_costs(user_id);
CREATE INDEX idx_daily_costs_date    ON daily_costs(date);

-- 1b. SERVICE_COSTS — One row per user per service per day
-- WHY: Enables per-service forecasting. "Your EC2 cost will rise but Lambda
--      will drop." Also feeds the service breakdown pie chart on dashboard.
--      365 days × 8 users × ~6 avg services = ~17,520 rows.

CREATE TABLE IF NOT EXISTS service_costs (
    date              TEXT    NOT NULL,                -- 'YYYY-MM-DD'
    user_id           TEXT    NOT NULL,
    service           TEXT    NOT NULL,                -- 'EC2','RDS','S3','Lambda','EBS',
                                                      -- 'DynamoDB','ElastiCache','ECS',
                                                      -- 'NATGateway','ELB'
    daily_cost        REAL    NOT NULL,
    PRIMARY KEY (date, user_id, service),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (service IN ('EC2','RDS','S3','Lambda','EBS',
                       'DynamoDB','ElastiCache','ECS',
                       'NATGateway','ELB'))
);

CREATE INDEX idx_service_costs_user    ON service_costs(user_id, service);
CREATE INDEX idx_service_costs_date    ON service_costs(date);

-- 1c. SERVICE_REGION_COSTS — Per-service, per-region daily breakdown
-- WHY: Enables region-level cost analysis. "Your EC2 in us-east-1 costs
--      3x more than eu-north-1." Feeds geographic cost visualisation.

CREATE TABLE IF NOT EXISTS service_region_costs (
    date              TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    service           TEXT    NOT NULL,
    region            TEXT    NOT NULL,
    daily_cost        REAL    NOT NULL,
    PRIMARY KEY (date, user_id, service, region),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_service_region_costs_user ON service_region_costs(user_id);
CREATE INDEX idx_service_region_costs_date ON service_region_costs(date);

-- ============================================================================
-- 2. METRICS TABLES — CloudWatch-style utilization data
-- ============================================================================
-- WHY metrics tables exist:
--   Metrics answer "HOW MUCH of the resource is actually being used?"
--   If CPU is 5% on a t3.large, the optimizer knows to downsize.
--   Each service has DIFFERENT metrics, so each gets its own table.

-- 2a. EC2_METRICS — Hourly compute metrics
-- 8 users × 8,760 hours = 70,080 rows

CREATE TABLE IF NOT EXISTS ec2_metrics (
    timestamp         TEXT    NOT NULL,                -- 'YYYY-MM-DD HH:MM:SS'
    user_id           TEXT    NOT NULL,
    instance_id       TEXT    NOT NULL,                -- 'i-user001-001'
    cpu_utilization   REAL    NOT NULL,                -- 0-100%
    cpu_max           REAL,                            -- Max CPU in period
    memory_utilization REAL,                           -- 0-100% (CloudWatch agent, may be NULL)
    network_in_kbps   REAL    NOT NULL DEFAULT 0,
    network_out_kbps  REAL    NOT NULL DEFAULT 0,
    disk_read_kbps    REAL    NOT NULL DEFAULT 0,
    disk_write_kbps   REAL    NOT NULL DEFAULT 0,
    disk_read_ops     REAL    DEFAULT 0,
    disk_write_ops    REAL    DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, instance_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_ec2_metrics_user      ON ec2_metrics(user_id);
CREATE INDEX idx_ec2_metrics_ts        ON ec2_metrics(timestamp);
CREATE INDEX idx_ec2_metrics_instance  ON ec2_metrics(instance_id);

-- 2b. RDS_METRICS — Hourly database metrics
-- 4 users × 8,760 hours = 35,040 rows

CREATE TABLE IF NOT EXISTS rds_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    db_instance_id    TEXT    NOT NULL,                -- 'db-user003-001'
    cpu_utilization   REAL    NOT NULL,
    memory_utilization REAL   NOT NULL,
    read_iops         REAL    NOT NULL DEFAULT 0,
    write_iops        REAL    NOT NULL DEFAULT 0,
    connections       INTEGER NOT NULL DEFAULT 0,
    free_storage_gb   REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, db_instance_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_rds_metrics_user ON rds_metrics(user_id);
CREATE INDEX idx_rds_metrics_ts   ON rds_metrics(timestamp);

-- 2c. ELASTICACHE_METRICS — Hourly cache metrics
-- 3 users × 8,760 hours = 26,280 rows

CREATE TABLE IF NOT EXISTS elasticache_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    cache_cluster_id  TEXT    NOT NULL,                -- 'cache-user003-001'
    cpu_utilization   REAL    NOT NULL,
    memory_utilization REAL   NOT NULL,
    curr_connections  INTEGER NOT NULL DEFAULT 0,
    cache_hits        INTEGER NOT NULL DEFAULT 0,      -- Per hour
    cache_misses      INTEGER NOT NULL DEFAULT 0,
    evictions         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, cache_cluster_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_elasticache_metrics_user ON elasticache_metrics(user_id);
CREATE INDEX idx_elasticache_metrics_ts   ON elasticache_metrics(timestamp);

-- 2d. ECS_METRICS — Hourly container metrics
-- 3 users × 8,760 hours = 26,280 rows

CREATE TABLE IF NOT EXISTS ecs_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    service_name      TEXT    NOT NULL,                -- 'ecs-user006-api'
    cluster_name      TEXT    NOT NULL,
    cpu_utilization   REAL    NOT NULL,                -- % of allocated CPU
    memory_utilization REAL   NOT NULL,                -- % of allocated memory
    running_task_count INTEGER NOT NULL DEFAULT 1,
    desired_task_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (timestamp, user_id, service_name),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_ecs_metrics_user ON ecs_metrics(user_id);
CREATE INDEX idx_ecs_metrics_ts   ON ecs_metrics(timestamp);

-- 2e. LAMBDA_METRICS — Daily aggregates (Lambda is event-driven, not continuous)
-- 6 users × 365 days × ~2 functions avg = ~4,380 rows

CREATE TABLE IF NOT EXISTS lambda_metrics (
    date              TEXT    NOT NULL,                -- 'YYYY-MM-DD'
    user_id           TEXT    NOT NULL,
    function_name     TEXT    NOT NULL,                -- 'fn-user002-api-handler'
    invocations       INTEGER NOT NULL DEFAULT 0,      -- Total that day
    avg_duration_ms   REAL    NOT NULL DEFAULT 0,
    max_duration_ms   REAL    NOT NULL DEFAULT 0,
    errors            INTEGER NOT NULL DEFAULT 0,
    throttles         INTEGER NOT NULL DEFAULT 0,
    avg_memory_used_mb REAL   NOT NULL DEFAULT 0,      -- Actual usage
    memory_allocated_mb INTEGER NOT NULL,              -- Configured limit
    PRIMARY KEY (date, user_id, function_name),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_lambda_metrics_user ON lambda_metrics(user_id);
CREATE INDEX idx_lambda_metrics_date ON lambda_metrics(date);

-- 2f. DYNAMODB_METRICS — Hourly table metrics
-- 3 users × 8,760 hours × ~1.5 tables avg = ~39,420 rows

CREATE TABLE IF NOT EXISTS dynamodb_metrics (
    timestamp              TEXT    NOT NULL,
    user_id                TEXT    NOT NULL,
    table_name             TEXT    NOT NULL,           -- 'ddb-user002-sessions'
    consumed_read_units    REAL    NOT NULL DEFAULT 0,
    consumed_write_units   REAL    NOT NULL DEFAULT 0,
    provisioned_read_units REAL    DEFAULT NULL,       -- NULL if On-Demand
    provisioned_write_units REAL   DEFAULT NULL,
    throttled_requests     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, table_name),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_dynamodb_metrics_user ON dynamodb_metrics(user_id);
CREATE INDEX idx_dynamodb_metrics_ts   ON dynamodb_metrics(timestamp);

-- 2g. EBS_METRICS — Hourly volume I/O metrics

CREATE TABLE IF NOT EXISTS ebs_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    volume_id         TEXT    NOT NULL,
    read_ops          REAL    NOT NULL DEFAULT 0,
    write_ops         REAL    NOT NULL DEFAULT 0,
    read_bytes        REAL    NOT NULL DEFAULT 0,
    write_bytes       REAL    NOT NULL DEFAULT 0,
    idle_time_seconds REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, volume_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_ebs_metrics_user ON ebs_metrics(user_id);
CREATE INDEX idx_ebs_metrics_ts   ON ebs_metrics(timestamp);

-- 2h. S3_METRICS — Periodic bucket size and object count

CREATE TABLE IF NOT EXISTS s3_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    bucket_name       TEXT    NOT NULL,
    bucket_size_bytes REAL    DEFAULT 0,
    number_of_objects INTEGER DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, bucket_name),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_s3_metrics_user ON s3_metrics(user_id);
CREATE INDEX idx_s3_metrics_ts   ON s3_metrics(timestamp);

-- 2i. NAT_GATEWAY_METRICS — Hourly NAT Gateway traffic metrics

CREATE TABLE IF NOT EXISTS nat_gateway_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    nat_gateway_id    TEXT    NOT NULL,
    bytes_in          REAL    NOT NULL DEFAULT 0,
    bytes_out         REAL    NOT NULL DEFAULT 0,
    packets_in        INTEGER NOT NULL DEFAULT 0,
    packets_out       INTEGER NOT NULL DEFAULT 0,
    active_connections INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, nat_gateway_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_nat_gateway_metrics_user ON nat_gateway_metrics(user_id);
CREATE INDEX idx_nat_gateway_metrics_ts   ON nat_gateway_metrics(timestamp);

-- 2j. ELB_METRICS — Hourly load balancer traffic and response metrics

CREATE TABLE IF NOT EXISTS elb_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    elb_arn           TEXT    NOT NULL,
    request_count     INTEGER NOT NULL DEFAULT 0,
    active_connections INTEGER NOT NULL DEFAULT 0,
    new_connections   INTEGER NOT NULL DEFAULT 0,
    processed_bytes   REAL    NOT NULL DEFAULT 0,
    http_2xx          INTEGER NOT NULL DEFAULT 0,
    http_3xx          INTEGER NOT NULL DEFAULT 0,
    http_4xx          INTEGER NOT NULL DEFAULT 0,
    http_5xx          INTEGER NOT NULL DEFAULT 0,
    target_response_time_avg REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, elb_arn),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_elb_metrics_user ON elb_metrics(user_id);
CREATE INDEX idx_elb_metrics_ts   ON elb_metrics(timestamp);

-- ============================================================================
-- 3. INVENTORY TABLES — What resources each user currently has
-- ============================================================================
-- WHY inventory tables exist:
--   Metrics tell you "how much is used." Inventory tells you "of what."
--   You need both: 15% CPU on a t3.micro is fine. 15% CPU on m5.4xlarge
--   means you're wasting $500/month.

-- 3a. EC2_INSTANCES — 8 rows (one per user, could be more)
CREATE TABLE IF NOT EXISTS ec2_instances (
    instance_id       TEXT    NOT NULL,                -- 'i-user001-001'
    user_id           TEXT    NOT NULL,
    instance_type     TEXT    NOT NULL,                -- 't3.medium', 'm5.xlarge'
    vcpus             INTEGER NOT NULL,
    memory_gb         REAL    NOT NULL,
    state             TEXT    NOT NULL DEFAULT 'running',
    launch_date       TEXT    NOT NULL,                -- 'YYYY-MM-DD'
    region            TEXT    NOT NULL DEFAULT 'us-east-1',
    availability_zone TEXT    NOT NULL DEFAULT 'us-east-1a',
    pricing_model     TEXT    NOT NULL DEFAULT 'on-demand',  -- 'on-demand','reserved','spot'
    monthly_cost      REAL    NOT NULL,
    PRIMARY KEY (instance_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (state IN ('running','stopped','terminated')),
    CHECK (pricing_model IN ('on-demand','reserved-1yr','reserved-3yr','spot'))
);

CREATE INDEX idx_ec2_instances_user ON ec2_instances(user_id);

-- 3b. RDS_INSTANCES — ~5 rows
CREATE TABLE IF NOT EXISTS rds_instances (
    db_instance_id    TEXT    NOT NULL,                -- 'db-user003-001'
    user_id           TEXT    NOT NULL,
    db_instance_class TEXT    NOT NULL,                -- 'db.t3.medium', 'db.r5.large'
    engine            TEXT    NOT NULL,                -- 'mysql','postgres','mariadb'
    engine_version    TEXT,
    storage_gb        INTEGER NOT NULL,
    storage_type      TEXT    NOT NULL DEFAULT 'gp3',  -- 'gp2','gp3','io1','io2'
    multi_az          INTEGER NOT NULL DEFAULT 0,      -- 0=false, 1=true
    pricing_model     TEXT    NOT NULL DEFAULT 'on-demand',
    monthly_cost      REAL    NOT NULL,
    PRIMARY KEY (db_instance_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (pricing_model IN ('on-demand','reserved-1yr','reserved-3yr'))
);

CREATE INDEX idx_rds_instances_user ON rds_instances(user_id);

-- 3c. ELASTICACHE_NODES — ~4 rows
CREATE TABLE IF NOT EXISTS elasticache_nodes (
    cache_cluster_id  TEXT    NOT NULL,                -- 'cache-user003-001'
    user_id           TEXT    NOT NULL,
    cache_node_type   TEXT    NOT NULL,                -- 'cache.t3.medium','cache.r5.large'
    engine            TEXT    NOT NULL,                -- 'redis','memcached'
    engine_version    TEXT,
    num_cache_nodes   INTEGER NOT NULL DEFAULT 1,
    pricing_model     TEXT    NOT NULL DEFAULT 'on-demand',
    monthly_cost      REAL    NOT NULL,
    PRIMARY KEY (cache_cluster_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (engine IN ('redis','memcached')),
    CHECK (pricing_model IN ('on-demand','reserved-1yr','reserved-3yr'))
);

CREATE INDEX idx_elasticache_nodes_user ON elasticache_nodes(user_id);

-- 3d. ECS_SERVICES — ~5 rows
CREATE TABLE IF NOT EXISTS ecs_services (
    service_name      TEXT    NOT NULL,                -- 'ecs-user006-api'
    user_id           TEXT    NOT NULL,
    cluster_name      TEXT    NOT NULL,                -- 'cluster-user006'
    launch_type       TEXT    NOT NULL DEFAULT 'FARGATE',  -- 'FARGATE','EC2'
    desired_count     INTEGER NOT NULL DEFAULT 1,      -- Number of tasks
    cpu               INTEGER NOT NULL,                -- Fargate CPU units (256/512/1024/2048/4096)
    memory_mb         INTEGER NOT NULL,                -- Fargate memory in MB
    monthly_cost      REAL    NOT NULL,
    PRIMARY KEY (service_name, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (launch_type IN ('FARGATE','EC2'))
);

CREATE INDEX idx_ecs_services_user ON ecs_services(user_id);

-- 3e. LAMBDA_FUNCTIONS — ~12 rows
CREATE TABLE IF NOT EXISTS lambda_functions (
    function_name     TEXT    NOT NULL,                -- 'fn-user002-api-handler'
    user_id           TEXT    NOT NULL,
    runtime           TEXT    NOT NULL,                -- 'python3.12','nodejs20.x'
    memory_mb         INTEGER NOT NULL,                -- 128, 256, 512, 1024, etc.
    timeout_sec       INTEGER NOT NULL DEFAULT 30,
    avg_daily_invocations INTEGER NOT NULL DEFAULT 0,
    avg_duration_ms   REAL    NOT NULL DEFAULT 0,
    monthly_cost      REAL    NOT NULL,
    PRIMARY KEY (function_name, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_lambda_functions_user ON lambda_functions(user_id);

-- 3f. EBS_VOLUMES — ~12 rows
CREATE TABLE IF NOT EXISTS ebs_volumes (
    volume_id         TEXT    NOT NULL,                -- 'vol-user001-001'
    user_id           TEXT    NOT NULL,
    volume_type       TEXT    NOT NULL,                -- 'gp2','gp3','io1','io2','st1','sc1'
    size_gb           INTEGER NOT NULL,
    iops              INTEGER,                         -- NULL for st1/sc1
    throughput_mbps   INTEGER,                         -- Only for gp3
    attached_instance_id TEXT,                         -- NULL if unattached (waste!)
    state             TEXT    NOT NULL DEFAULT 'in-use',  -- 'in-use','available'
    monthly_cost      REAL    NOT NULL,
    PRIMARY KEY (volume_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (volume_type IN ('gp2','gp3','io1','io2','st1','sc1')),
    CHECK (state IN ('in-use','available'))
);

CREATE INDEX idx_ebs_volumes_user ON ebs_volumes(user_id);

-- 3g. S3_BUCKETS — ~12 rows
CREATE TABLE IF NOT EXISTS s3_buckets (
    bucket_name       TEXT    NOT NULL,                -- 's3-user001-blog-assets'
    user_id           TEXT    NOT NULL,
    storage_class     TEXT    NOT NULL DEFAULT 'STANDARD',
    size_gb           REAL    NOT NULL,
    num_objects       INTEGER NOT NULL DEFAULT 0,
    avg_daily_get_requests INTEGER NOT NULL DEFAULT 0,
    avg_daily_put_requests INTEGER NOT NULL DEFAULT 0,
    monthly_cost      REAL    NOT NULL,
    PRIMARY KEY (bucket_name, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (storage_class IN ('STANDARD','STANDARD_IA','ONEZONE_IA',
                             'INTELLIGENT_TIERING','GLACIER','DEEP_ARCHIVE'))
);

CREATE INDEX idx_s3_buckets_user ON s3_buckets(user_id);

-- 3h. DYNAMODB_TABLES — ~6 rows
CREATE TABLE IF NOT EXISTS dynamodb_tables (
    table_name        TEXT    NOT NULL,                -- 'ddb-user002-sessions'
    user_id           TEXT    NOT NULL,
    capacity_mode     TEXT    NOT NULL,                -- 'PROVISIONED','ON_DEMAND'
    provisioned_rcu   INTEGER DEFAULT NULL,            -- NULL if On-Demand
    provisioned_wcu   INTEGER DEFAULT NULL,
    storage_gb        REAL    NOT NULL DEFAULT 0,
    item_count        INTEGER NOT NULL DEFAULT 0,
    monthly_cost      REAL    NOT NULL,
    PRIMARY KEY (table_name, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (capacity_mode IN ('PROVISIONED','ON_DEMAND'))
);

CREATE INDEX idx_dynamodb_tables_user ON dynamodb_tables(user_id);

-- 3i. NAT_GATEWAYS — ~5 rows
CREATE TABLE IF NOT EXISTS nat_gateways (
    nat_gateway_id    TEXT    NOT NULL,                -- 'nat-user002-001'
    user_id           TEXT    NOT NULL,
    vpc_id            TEXT    NOT NULL,
    subnet_id         TEXT    NOT NULL,
    state             TEXT    NOT NULL DEFAULT 'available',
    monthly_hours     REAL    NOT NULL DEFAULT 730,    -- ~730 hrs/month
    monthly_data_processed_gb REAL NOT NULL DEFAULT 0,
    monthly_cost      REAL    NOT NULL,                -- $0.045/hr + $0.045/GB
    PRIMARY KEY (nat_gateway_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_nat_gateways_user ON nat_gateways(user_id);

-- 3j. ELB_INSTANCES — ~5 rows
CREATE TABLE IF NOT EXISTS elb_instances (
    elb_arn           TEXT    NOT NULL,                -- 'arn:aws:...:elb-user002-001'
    user_id           TEXT    NOT NULL,
    elb_name          TEXT    NOT NULL,                -- 'elb-user002-001'
    elb_type          TEXT    NOT NULL,                -- 'ALB','NLB','CLB'
    scheme            TEXT    NOT NULL DEFAULT 'internet-facing',
    target_count      INTEGER NOT NULL DEFAULT 0,
    healthy_target_count INTEGER NOT NULL DEFAULT 0,
    avg_daily_requests INTEGER NOT NULL DEFAULT 0,
    monthly_cost      REAL    NOT NULL,
    PRIMARY KEY (elb_arn, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (elb_type IN ('ALB','NLB','CLB')),
    CHECK (scheme IN ('internet-facing','internal'))
);

CREATE INDEX idx_elb_instances_user ON elb_instances(user_id);

-- ============================================================================
-- 4. PRICING TABLE — Reference data for the optimizer
-- ============================================================================
-- WHY one table for EC2/RDS/ElastiCache:
--   All three use the SAME pricing model: instance types with
--   On-Demand vs Reserved vs Spot tiers. The optimizer runs the
--   same MILP algorithm across all three.
--
-- Services like S3, Lambda, DynamoDB have DIFFERENT pricing models
-- (per-GB, per-request, per-capacity-unit). Those are stored as
-- constants in the optimizer code, not in this table.

CREATE TABLE IF NOT EXISTS instance_pricing (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    service               TEXT    NOT NULL,            -- 'EC2','RDS','ElastiCache'
    instance_type         TEXT    NOT NULL,            -- 't3.micro','db.t3.micro','cache.t3.micro'
    vcpus                 INTEGER NOT NULL,
    memory_gb             REAL    NOT NULL,
    category              TEXT,                        -- 'general','compute','memory'
    on_demand_hourly      REAL    NOT NULL,
    reserved_1yr_hourly   REAL    NOT NULL,
    reserved_3yr_hourly   REAL,                        -- NULL if not available
    spot_hourly           REAL,                        -- NULL for RDS/ElastiCache
    on_demand_monthly     REAL    NOT NULL,            -- hourly × 730
    reserved_1yr_monthly  REAL    NOT NULL,
    reserved_3yr_monthly  REAL,
    spot_monthly          REAL,
    UNIQUE(service, instance_type),
    CHECK (service IN ('EC2','RDS','ElastiCache'))
);

CREATE INDEX idx_pricing_service ON instance_pricing(service);
CREATE INDEX idx_pricing_type    ON instance_pricing(instance_type);

-- ============================================================================
-- 5. OUTPUT TABLES — What the system produces
-- ============================================================================

-- 5a. AI_RECOMMENDATIONS — For new users (no AWS data yet)
-- WHY: When user_type='new', the AI module asks questions and generates
--      a recommendation via LLM. Store the input, output, and prompt
--      so we can show it on the dashboard and compare with ML results later.

CREATE TABLE IF NOT EXISTS ai_recommendations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT    NOT NULL,
    -- User's answers to the questionnaire
    app_type          TEXT    NOT NULL,                -- 'website','api','database','ml_training',...
    expected_users    INTEGER,                         -- Daily active users
    uptime_hours      INTEGER,                         -- Hours per day
    importance        TEXT,                            -- 'low','medium','high','critical'
    budget_monthly    REAL,                            -- Max budget in USD
    extra_requirements TEXT,                           -- Free text from user
    -- What was sent to the LLM
    prompt_text       TEXT    NOT NULL,                -- The structured prompt we built
    -- What the LLM returned
    recommended_setup TEXT    NOT NULL,                -- JSON: instance type, region, services
    estimated_cost    REAL    NOT NULL,                -- LLM's cost estimate
    explanation       TEXT,                            -- LLM's reasoning
    llm_model         TEXT    NOT NULL,                -- 'gpt-4o-mini','bedrock-claude', etc.
    llm_response_raw  TEXT,                            -- Full raw response for debugging
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_ai_rec_user ON ai_recommendations(user_id);

-- 5b. FORECASTS — Model-agnostic prediction storage
-- WHY: Dashboard needs to show "predicted cost for next 30 days."
--      Store predictions so we don't re-run any model every page load.
--      Schema works with ANY forecasting model: Prophet, SARIMAX, LSTM,
--      XGBoost, ARIMA, Holt-Winters, or any future model.

CREATE TABLE IF NOT EXISTS forecasts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT    NOT NULL,
    service           TEXT,                            -- NULL = total cost, else specific service
    forecast_date     TEXT    NOT NULL,                -- The date being predicted
    predicted_cost    REAL    NOT NULL,
    lower_bound       REAL,                            -- Lower confidence interval (e.g. 80% CI)
    upper_bound       REAL,                            -- Upper confidence interval (e.g. 80% CI)
    model_type        TEXT    NOT NULL,                -- Which model produced this: any string
    model_params      TEXT,                            -- JSON blob of model hyperparameters (optional)
    mae               REAL,                            -- Mean Absolute Error on validation set
    mape              REAL,                            -- Mean Absolute Percentage Error
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_forecasts_user    ON forecasts(user_id);
CREATE INDEX idx_forecasts_date    ON forecasts(forecast_date);
CREATE INDEX idx_forecasts_service ON forecasts(user_id, service);

-- 5c. RECOMMENDATIONS — Optimizer output
-- WHY: This is the core value of the system. Each row is one actionable
--      recommendation like "Downsize EC2 from m5.xlarge to t3.medium."

CREATE TABLE IF NOT EXISTS recommendations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT    NOT NULL,
    service           TEXT    NOT NULL,                -- 'EC2','RDS','S3', etc.
    resource_id       TEXT    NOT NULL,                -- 'i-user001-001','s3-user001-blog'
    recommendation_type TEXT  NOT NULL,                -- See CHECK constraint below
    current_config    TEXT    NOT NULL,                -- 't3.large, on-demand'
    recommended_config TEXT   NOT NULL,                -- 't3.small, reserved-1yr'
    current_monthly_cost   REAL NOT NULL,
    estimated_monthly_cost REAL NOT NULL,
    monthly_savings   REAL    NOT NULL,                -- current - estimated
    savings_percent   REAL    NOT NULL,                -- (savings / current) × 100
    confidence        TEXT    NOT NULL DEFAULT 'medium', -- 'high','medium','low'
    reasoning         TEXT,                            -- Human-readable explanation
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (recommendation_type IN (
        'rightsize',              -- EC2/RDS/ElastiCache/ECS: change instance size
        'pricing_plan_switch',    -- EC2/RDS/ElastiCache: On-Demand → Reserved/Spot
        'storage_class_switch',   -- S3: Standard → IA
        'memory_resize',          -- Lambda: reduce allocated memory
        'volume_type_upgrade',    -- EBS: gp2 → gp3
        'delete_unused',          -- EBS: delete unattached volumes
        'capacity_mode_switch',   -- DynamoDB: Provisioned → On-Demand
        'replace_with_endpoint',  -- NAT: use VPC endpoints instead
        'delete_idle'             -- ELB: delete load balancer with 0 targets
    )),
    CHECK (confidence IN ('high','medium','low'))
);

CREATE INDEX idx_recommendations_user    ON recommendations(user_id);
CREATE INDEX idx_recommendations_service ON recommendations(service);

-- ============================================================================
-- 6. ANOMALIES TABLE — Detected cost spikes
-- ============================================================================
-- WHY: The anomaly detection module flags unusual cost days.
--      Stored here so the dashboard can highlight them.

CREATE TABLE IF NOT EXISTS anomalies (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT    NOT NULL,
    service           TEXT,                            -- NULL = total cost anomaly
    anomaly_date      TEXT    NOT NULL,
    expected_cost     REAL    NOT NULL,
    actual_cost       REAL    NOT NULL,
    deviation_percent REAL    NOT NULL,                -- How far from expected
    severity          TEXT    NOT NULL DEFAULT 'warning',
    description       TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (severity IN ('info','warning','critical'))
);

CREATE INDEX idx_anomalies_user ON anomalies(user_id);
CREATE INDEX idx_anomalies_date ON anomalies(anomaly_date);

-- ============================================================================
-- SUMMARY — 30 tables
-- ============================================================================
--
-- CORE (2 tables):
--   1  users                    (auth + profile + user_type)
--   2  aws_connections          (IAM Role ARN — NO secret keys stored)
--
-- COST DATA (3 tables):
--   3  daily_costs              (365 days × N users)
--   4  service_costs            (per-service daily breakdown)
--   5  service_region_costs     (per-service per-region daily breakdown)
--
-- METRICS (11 tables — CloudWatch-style):
--   6  ec2_metrics              (hourly compute metrics)
--   7  rds_metrics              (hourly database metrics)
--   8  elasticache_metrics      (hourly cache metrics)
--   9  ecs_metrics              (hourly container metrics)
--   10 lambda_metrics           (daily function metrics)
--   11 dynamodb_metrics         (hourly table metrics)
--   12 ebs_metrics              (hourly volume I/O)
--   13 s3_metrics               (periodic bucket size)
--   14 nat_gateway_metrics      (hourly NAT traffic)
--   15 elb_metrics              (hourly load balancer traffic)
--
-- INVENTORY (10 tables — one per service):
--   16 ec2_instances
--   17 rds_instances
--   18 elasticache_nodes
--   19 ecs_services
--   20 lambda_functions
--   21 ebs_volumes
--   22 s3_buckets
--   23 dynamodb_tables
--   24 nat_gateways
--   25 elb_instances
--
-- PRICING (1 table):
--   26 instance_pricing         (EC2/RDS/ElastiCache)
--
-- OUTPUT (4 tables — system produces these):
--   27 ai_recommendations       (new users — LLM responses)
--   28 forecasts                (ML predictions — any model)
--   29 recommendations          (optimizer — rightsizing/plan switch)
--   30 anomalies                (detected cost spikes)
--
-- ============================================================================