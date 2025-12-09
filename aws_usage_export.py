import boto3
import csv
from datetime import datetime, timedelta, timezone

# ========= General Settings =========

DAYS_BACK = 150                # تقريباً 5 شهور
EC2_PERIOD_SECONDS = 3600     # 3 ساعات
DEFAULT_PERIOD_SECONDS = 3600  # ساعة لباقي الخدمات
DAILY_PERIOD_SECONDS = 86400   # يوم واحد (لبعض metrics زي S3)

# ========= CSV Filenames =========

EC2_INSTANCES_CSV = "ec2_instances.csv"
EC2_METRICS_CSV = "ec2_metrics.csv"

EBS_VOLUMES_CSV = "ebs_volumes.csv"
EBS_METRICS_CSV = "ebs_metrics.csv"

RDS_INSTANCES_CSV = "rds_instances.csv"
RDS_METRICS_CSV = "rds_metrics.csv"

S3_BUCKETS_CSV = "s3_buckets.csv"
S3_STORAGE_CSV = "s3_storage_metrics.csv"

ELB_CSV = "elbv2_load_balancers.csv"
ELB_METRICS_CSV = "elbv2_metrics.csv"

LAMBDA_FUNCTIONS_CSV = "lambda_functions.csv"
LAMBDA_METRICS_CSV = "lambda_metrics.csv"

DAILY_COST_CSV = "daily_cost_by_service.csv"
DAILY_COST_REGION_CSV = "daily_cost_by_service_region.csv"
DAILY_COST_TAG_ENV_CSV = "daily_cost_by_tag_Environment.csv"


# ========= Time Helpers =========

def get_time_range(days_back: int):
    """Return start_time and end_time for CloudWatch metrics."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    return start, end


def get_date_range_for_cost(days_back: int):
    """Return start_date and end_date for Cost Explorer."""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days_back)
    # Cost Explorer uses date only; end is exclusive
    return start_date.isoformat(), end_date.isoformat()


# ========= CloudWatch Metrics Helper =========

def fetch_metric(
    cloudwatch_client,
    namespace: str,
    metric_name: str,
    dimensions: list[dict],
    start_time,
    end_time,
    period: int,
    statistics: list[str]
):
    try:
        response = cloudwatch_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=statistics,
        )
        return response.get("Datapoints", [])
    except Exception as e:
        print(f"[WARN] Failed to fetch metric {namespace}/{metric_name}: {e}")
        return []


# ========= EC2: Inventory =========

def export_ec2_instances(session, account_id: str, regions: list[str]):
    """Export detailed EC2 inventory to CSV."""
    rows = []

    for region in regions:
        print(f"[EC2] Scanning region {region} ...")
        ec2 = session.client("ec2", region_name=region)

        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    instance_id = inst["InstanceId"]
                    instance_type = inst.get("InstanceType", "")
                    state = inst.get("State", {}).get("Name", "")
                    launch_time = inst.get("LaunchTime")
                    az = inst.get("Placement", {}).get("AvailabilityZone", "")

                    private_ip = inst.get("PrivateIpAddress")
                    public_ip = inst.get("PublicIpAddress")
                    vpc_id = inst.get("VpcId")
                    subnet_id = inst.get("SubnetId")
                    ami = inst.get("ImageId")
                    tenancy = inst.get("Placement", {}).get("Tenancy")
                    hypervisor = inst.get("Hypervisor")
                    architecture = inst.get("Architecture")

                    # Monitoring
                    monitoring = inst.get("Monitoring", {}).get("State")

                    # CPU options
                    cpu_cores = inst.get("CpuOptions", {}).get("CoreCount")
                    threads_per_core = inst.get("CpuOptions", {}).get("ThreadsPerCore")

                    # Security Groups
                    sgs = ";".join(sg["GroupId"] for sg in inst.get("SecurityGroups", []))

                    # EBS volumes
                    ebs_volumes = []
                    for block in inst.get("BlockDeviceMappings", []):
                        if "Ebs" in block:
                            ebs_volumes.append(block["Ebs"]["VolumeId"])
                    ebs_volumes_str = ";".join(ebs_volumes)

                    # Network interfaces
                    eni_ids = []
                    for eni in inst.get("NetworkInterfaces", []):
                        eni_ids.append(eni.get("NetworkInterfaceId"))
                    eni_str = ";".join(e for e in eni_ids if e)

                    # Tags
                    tags = inst.get("Tags", [])
                    tag_str = ";".join(
                        f"{t.get('Key','')}={t.get('Value','')}" for t in tags
                    )

                    rows.append({
                        "account_id": account_id,
                        "region": region,
                        "instance_id": instance_id,
                        "instance_type": instance_type,
                        "state": state,
                        "availability_zone": az,
                        "launch_time": launch_time.isoformat() if launch_time else "",
                        "private_ip": private_ip,
                        "public_ip": public_ip,
                        "vpc_id": vpc_id,
                        "subnet_id": subnet_id,
                        "ami_id": ami,
                        "tenancy": tenancy,
                        "hypervisor": hypervisor,
                        "architecture": architecture,
                        "monitoring": monitoring,
                        "cpu_cores": cpu_cores,
                        "threads_per_core": threads_per_core,
                        "security_groups": sgs,
                        "ebs_volumes": ebs_volumes_str,
                        "network_interfaces": eni_str,
                        "tags": tag_str,
                    })

    fieldnames = [
        "account_id",
        "region",
        "instance_id",
        "instance_type",
        "state",
        "availability_zone",
        "launch_time",
        "private_ip",
        "public_ip",
        "vpc_id",
        "subnet_id",
        "ami_id",
        "tenancy",
        "hypervisor",
        "architecture",
        "monitoring",
        "cpu_cores",
        "threads_per_core",
        "security_groups",
        "ebs_volumes",
        "network_interfaces",
        "tags",
    ]

    print(f"[EC2] Writing {len(rows)} instances to {EC2_INSTANCES_CSV} ...")
    with open(EC2_INSTANCES_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= EC2: Metrics =========

def export_ec2_metrics(session, account_id: str, regions: list[str]):
    """Export EC2 metrics (CPU, network, disk, memory if available) to CSV."""
    start_time, end_time = get_time_range(DAYS_BACK)
    rows = []

    for region in regions:
        print(f"[Metrics] Processing EC2 metrics in region {region} ...")
        ec2 = session.client("ec2", region_name=region)
        cloudwatch = session.client("cloudwatch", region_name=region)

        paginator = ec2.get_paginator("describe_instances")
        instance_ids = []
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    if inst.get("State", {}).get("Name") == "running":
                        instance_ids.append(inst["InstanceId"])

        if not instance_ids:
            continue

        for instance_id in instance_ids:
            print(f"  [Metrics] EC2 Instance {instance_id}")
            dims = [{"Name": "InstanceId", "Value": instance_id}]

            cpu_points = fetch_metric(
                cloudwatch,
                namespace="AWS/EC2",
                metric_name="CPUUtilization",
                dimensions=dims,
                start_time=start_time,
                end_time=end_time,
                period=EC2_PERIOD_SECONDS,
                statistics=["Average", "Maximum"],
            )
            net_in_points = fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "NetworkIn",
                dims,
                start_time,
                end_time,
                EC2_PERIOD_SECONDS,
                ["Average"],
            )
            net_out_points = fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "NetworkOut",
                dims,
                start_time,
                end_time,
                EC2_PERIOD_SECONDS,
                ["Average"],
            )
            disk_read_ops_points = fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "DiskReadOps",
                dims,
                start_time,
                end_time,
                EC2_PERIOD_SECONDS,
                ["Average"],
            )
            disk_write_ops_points = fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "DiskWriteOps",
                dims,
                start_time,
                end_time,
                EC2_PERIOD_SECONDS,
                ["Average"],
            )
            disk_read_bytes_points = fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "DiskReadBytes",
                dims,
                start_time,
                end_time,
                EC2_PERIOD_SECONDS,
                ["Average"],
            )
            disk_write_bytes_points = fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "DiskWriteBytes",
                dims,
                start_time,
                end_time,
                EC2_PERIOD_SECONDS,
                ["Average"],
            )
            status_check_points = fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "StatusCheckFailed",
                dims,
                start_time,
                end_time,
                EC2_PERIOD_SECONDS,
                ["Maximum"],
            )

            # Memory metric via CloudWatch Agent (if configured)
            mem_points = fetch_metric(
                cloudwatch,
                "CWAgent",
                "mem_used_percent",
                dims,
                start_time,
                end_time,
                EC2_PERIOD_SECONDS,
                ["Average"],
            )

            ts_map: dict[datetime, dict] = {}

            def merge_points(points, key_prefix, has_max=False):
                for p in points:
                    ts = p["Timestamp"]
                    entry = ts_map.setdefault(ts, {})
                    if "Average" in p:
                        entry[f"{key_prefix}_avg"] = p["Average"]
                    if has_max and "Maximum" in p:
                        entry[f"{key_prefix}_max"] = p["Maximum"]

            merge_points(cpu_points, "cpu", has_max=True)
            merge_points(net_in_points, "network_in", False)
            merge_points(net_out_points, "network_out", False)
            merge_points(disk_read_ops_points, "disk_read_ops", False)
            merge_points(disk_write_ops_points, "disk_write_ops", False)
            merge_points(disk_read_bytes_points, "disk_read_bytes", False)
            merge_points(disk_write_bytes_points, "disk_write_bytes", False)
            merge_points(status_check_points, "status_check_failed", True)
            merge_points(mem_points, "memory_used_percent", False)

            for ts, metrics in ts_map.items():
                rows.append({
                    "account_id": account_id,
                    "region": region,
                    "instance_id": instance_id,
                    "timestamp": ts.isoformat(),
                    "cpu_avg": metrics.get("cpu_avg"),
                    "cpu_max": metrics.get("cpu_max"),
                    "network_in_avg": metrics.get("network_in_avg"),
                    "network_out_avg": metrics.get("network_out_avg"),
                    "disk_read_ops_avg": metrics.get("disk_read_ops_avg"),
                    "disk_write_ops_avg": metrics.get("disk_write_ops_avg"),
                    "disk_read_bytes_avg": metrics.get("disk_read_bytes_avg"),
                    "disk_write_bytes_avg": metrics.get("disk_write_bytes_avg"),
                    "status_check_failed_max": metrics.get("status_check_failed_max"),
                    "memory_used_percent_avg": metrics.get("memory_used_percent_avg"),
                    "period_seconds": EC2_PERIOD_SECONDS,
                })

    fieldnames = [
        "account_id",
        "region",
        "instance_id",
        "timestamp",
        "cpu_avg",
        "cpu_max",
        "network_in_avg",
        "network_out_avg",
        "disk_read_ops_avg",
        "disk_write_ops_avg",
        "disk_read_bytes_avg",
        "disk_write_bytes_avg",
        "status_check_failed_max",
        "memory_used_percent_avg",
        "period_seconds",
    ]

    print(f"[Metrics] Writing {len(rows)} rows to {EC2_METRICS_CSV} ...")
    with open(EC2_METRICS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= EBS: Inventory =========

def export_ebs_volumes(session, account_id: str, regions: list[str]):
    rows = []

    for region in regions:
        print(f"[EBS] Scanning region {region} ...")
        ec2 = session.client("ec2", region_name=region)

        paginator = ec2.get_paginator("describe_volumes")
        for page in paginator.paginate():
            for vol in page.get("Volumes", []):
                volume_id = vol["VolumeId"]
                size = vol.get("Size")
                vol_type = vol.get("VolumeType")
                iops = vol.get("Iops")
                throughput = vol.get("Throughput")
                encrypted = vol.get("Encrypted")
                state = vol.get("State")
                az = vol.get("AvailabilityZone")
                create_time = vol.get("CreateTime")
                snap_id = vol.get("SnapshotId")

                attachments = vol.get("Attachments", [])
                attached_instances = ";".join(
                    f"{a.get('InstanceId')}:{a.get('Device')}"
                    for a in attachments
                    if a.get("InstanceId")
                )

                tags = vol.get("Tags", [])
                tag_str = ";".join(
                    f"{t.get('Key','')}={t.get('Value','')}" for t in tags
                )

                rows.append({
                    "account_id": account_id,
                    "region": region,
                    "volume_id": volume_id,
                    "size_gb": size,
                    "volume_type": vol_type,
                    "iops": iops,
                    "throughput": throughput,
                    "encrypted": encrypted,
                    "state": state,
                    "availability_zone": az,
                    "snapshot_id": snap_id,
                    "create_time": create_time.isoformat() if create_time else "",
                    "attachments": attached_instances,
                    "tags": tag_str,
                })

    fieldnames = [
        "account_id",
        "region",
        "volume_id",
        "size_gb",
        "volume_type",
        "iops",
        "throughput",
        "encrypted",
        "state",
        "availability_zone",
        "snapshot_id",
        "create_time",
        "attachments",
        "tags",
    ]

    print(f"[EBS] Writing {len(rows)} volumes to {EBS_VOLUMES_CSV} ...")
    with open(EBS_VOLUMES_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= EBS: Metrics =========

def export_ebs_metrics(session, account_id: str, regions: list[str]):
    start_time, end_time = get_time_range(DAYS_BACK)
    rows = []

    for region in regions:
        print(f"[Metrics] Processing EBS metrics in region {region} ...")
        ec2 = session.client("ec2", region_name=region)
        cloudwatch = session.client("cloudwatch", region_name=region)

        volumes = []
        paginator = ec2.get_paginator("describe_volumes")
        for page in paginator.paginate():
            for vol in page.get("Volumes", []):
                volumes.append(vol["VolumeId"])

        if not volumes:
            continue

        for volume_id in volumes:
            print(f"  [Metrics] EBS Volume {volume_id}")
            dims = [{"Name": "VolumeId", "Value": volume_id}]

            read_ops = fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "VolumeReadOps",
                dims,
                start_time,
                end_time,
                DEFAULT_PERIOD_SECONDS,
                ["Average"],
            )
            write_ops = fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "VolumeWriteOps",
                dims,
                start_time,
                end_time,
                DEFAULT_PERIOD_SECONDS,
                ["Average"],
            )
            read_bytes = fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "VolumeReadBytes",
                dims,
                start_time,
                end_time,
                DEFAULT_PERIOD_SECONDS,
                ["Average"],
            )
            write_bytes = fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "VolumeWriteBytes",
                dims,
                start_time,
                end_time,
                DEFAULT_PERIOD_SECONDS,
                ["Average"],
            )
            queue_length = fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "VolumeQueueLength",
                dims,
                start_time,
                end_time,
                DEFAULT_PERIOD_SECONDS,
                ["Average"],
            )
            burst_balance = fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "BurstBalance",
                dims,
                start_time,
                end_time,
                DEFAULT_PERIOD_SECONDS,
                ["Average"],
            )

            ts_map: dict[datetime, dict] = {}

            def merge(points, key):
                for p in points:
                    ts = p["Timestamp"]
                    entry = ts_map.setdefault(ts, {})
                    if "Average" in p:
                        entry[f"{key}_avg"] = p["Average"]

            merge(read_ops, "read_ops")
            merge(write_ops, "write_ops")
            merge(read_bytes, "read_bytes")
            merge(write_bytes, "write_bytes")
            merge(queue_length, "queue_length")
            merge(burst_balance, "burst_balance")

            for ts, metrics in ts_map.items():
                rows.append({
                    "account_id": account_id,
                    "region": region,
                    "volume_id": volume_id,
                    "timestamp": ts.isoformat(),
                    "read_ops_avg": metrics.get("read_ops_avg"),
                    "write_ops_avg": metrics.get("write_ops_avg"),
                    "read_bytes_avg": metrics.get("read_bytes_avg"),
                    "write_bytes_avg": metrics.get("write_bytes_avg"),
                    "queue_length_avg": metrics.get("queue_length_avg"),
                    "burst_balance_avg": metrics.get("burst_balance_avg"),
                    "period_seconds": DEFAULT_PERIOD_SECONDS,
                })

    fieldnames = [
        "account_id",
        "region",
        "volume_id",
        "timestamp",
        "read_ops_avg",
        "write_ops_avg",
        "read_bytes_avg",
        "write_bytes_avg",
        "queue_length_avg",
        "burst_balance_avg",
        "period_seconds",
    ]

    print(f"[Metrics] Writing {len(rows)} rows to {EBS_METRICS_CSV} ...")
    with open(EBS_METRICS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= RDS: Inventory =========

def export_rds_instances(session, account_id: str, regions: list[str]):
    rows = []

    for region in regions:
        print(f"[RDS] Scanning region {region} ...")
        rds = session.client("rds", region_name=region)

        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for db in page.get("DBInstances", []):
                tags = []
                try:
                    arn = db.get("DBInstanceArn")
                    if arn:
                        tag_list = rds.list_tags_for_resource(ResourceName=arn)
                        tags = tag_list.get("TagList", [])
                except Exception:
                    pass

                tag_str = ";".join(
                    f"{t.get('Key','')}={t.get('Value','')}" for t in tags
                )

                rows.append({
                    "account_id": account_id,
                    "region": region,
                    "db_instance_id": db["DBInstanceIdentifier"],
                    "engine": db["Engine"],
                    "engine_version": db["EngineVersion"],
                    "db_instance_class": db["DBInstanceClass"],
                    "multi_az": db.get("MultiAZ"),
                    "allocated_storage_gb": db.get("AllocatedStorage"),
                    "storage_type": db.get("StorageType"),
                    "iops": db.get("Iops"),
                    "status": db.get("DBInstanceStatus"),
                    "endpoint": db.get("Endpoint", {}).get("Address"),
                    "port": db.get("Endpoint", {}).get("Port"),
                    "publicly_accessible": db.get("PubliclyAccessible"),
                    "max_allocated_storage": db.get("MaxAllocatedStorage"),
                    "backup_retention_period": db.get("BackupRetentionPeriod"),
                    "auto_minor_version_upgrade": db.get("AutoMinorVersionUpgrade"),
                    "deletion_protection": db.get("DeletionProtection"),
                    "instance_create_time": str(db.get("InstanceCreateTime")),
                    "tags": tag_str,
                })

    fieldnames = [
        "account_id",
        "region",
        "db_instance_id",
        "engine",
        "engine_version",
        "db_instance_class",
        "multi_az",
        "allocated_storage_gb",
        "storage_type",
        "iops",
        "status",
        "endpoint",
        "port",
        "publicly_accessible",
        "max_allocated_storage",
        "backup_retention_period",
        "auto_minor_version_upgrade",
        "deletion_protection",
        "instance_create_time",
        "tags",
    ]

    print(f"[RDS] Writing {len(rows)} DB instances to {RDS_INSTANCES_CSV} ...")
    with open(RDS_INSTANCES_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= RDS: Metrics =========

def export_rds_metrics(session, account_id: str, regions: list[str]):
    start_time, end_time = get_time_range(DAYS_BACK)
    rows = []

    for region in regions:
        print(f"[Metrics] Processing RDS metrics in region {region} ...")
        rds = session.client("rds", region_name=region)
        cloudwatch = session.client("cloudwatch", region_name=region)

        db_ids = []
        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for db in page.get("DBInstances", []):
                db_ids.append(db["DBInstanceIdentifier"])

        if not db_ids:
            continue

        for db_id in db_ids:
            print(f"  [Metrics] RDS Instance {db_id}")
            dims = [{"Name": "DBInstanceIdentifier", "Value": db_id}]

            metrics_to_fetch = {
                "CPUUtilization": "cpu_util",
                "FreeStorageSpace": "free_storage",
                "FreeableMemory": "free_mem",
                "DatabaseConnections": "db_conns",
                "ReadIOPS": "read_iops",
                "WriteIOPS": "write_iops",
                "ReadLatency": "read_latency",
                "WriteLatency": "write_latency",
                "DiskQueueDepth": "queue_depth",
                "NetworkReceiveThroughput": "net_rx",
                "NetworkTransmitThroughput": "net_tx",
            }

            ts_map: dict[datetime, dict] = {}

            for metric_name, key_prefix in metrics_to_fetch.items():
                points = fetch_metric(
                    cloudwatch,
                    "AWS/RDS",
                    metric_name,
                    dims,
                    start_time,
                    end_time,
                    DEFAULT_PERIOD_SECONDS,
                    ["Average"],
                )
                for p in points:
                    ts = p["Timestamp"]
                    entry = ts_map.setdefault(ts, {})
                    if "Average" in p:
                        entry[f"{key_prefix}_avg"] = p["Average"]

            for ts, metrics in ts_map.items():
                rows.append({
                    "account_id": account_id,
                    "region": region,
                    "db_instance_id": db_id,
                    "timestamp": ts.isoformat(),
                    "cpu_util_avg": metrics.get("cpu_util_avg"),
                    "free_storage_avg": metrics.get("free_storage_avg"),
                    "free_mem_avg": metrics.get("free_mem_avg"),
                    "db_conns_avg": metrics.get("db_conns_avg"),
                    "read_iops_avg": metrics.get("read_iops_avg"),
                    "write_iops_avg": metrics.get("write_iops_avg"),
                    "read_latency_avg": metrics.get("read_latency_avg"),
                    "write_latency_avg": metrics.get("write_latency_avg"),
                    "queue_depth_avg": metrics.get("queue_depth_avg"),
                    "net_rx_avg": metrics.get("net_rx_avg"),
                    "net_tx_avg": metrics.get("net_tx_avg"),
                    "period_seconds": DEFAULT_PERIOD_SECONDS,
                })

    fieldnames = [
        "account_id",
        "region",
        "db_instance_id",
        "timestamp",
        "cpu_util_avg",
        "free_storage_avg",
        "free_mem_avg",
        "db_conns_avg",
        "read_iops_avg",
        "write_iops_avg",
        "read_latency_avg",
        "write_latency_avg",
        "queue_depth_avg",
        "net_rx_avg",
        "net_tx_avg",
        "period_seconds",
    ]

    print(f"[Metrics] Writing {len(rows)} rows to {RDS_METRICS_CSV} ...")
    with open(RDS_METRICS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= S3: Inventory =========

def export_s3_buckets(session, account_id: str):
    rows = []
    s3 = session.client("s3")

    print("[S3] Listing buckets ...")
    resp = s3.list_buckets()
    buckets = resp.get("Buckets", [])

    for b in buckets:
        name = b["Name"]
        create_date = b.get("CreationDate")
        create_str = create_date.isoformat() if create_date else ""

        # Region
        try:
            loc = s3.get_bucket_location(Bucket=name)
            region = loc.get("LocationConstraint") or "us-east-1"
        except Exception as e:
            print(f"[WARN] Failed to get location for bucket {name}: {e}")
            region = "unknown"

        # Versioning
        versioning_status = ""
        try:
            v = s3.get_bucket_versioning(Bucket=name)
            versioning_status = v.get("Status", "")
        except Exception:
            pass

        # Encryption
        encryption = ""
        try:
            enc = s3.get_bucket_encryption(Bucket=name)
            rules = enc["ServerSideEncryptionConfiguration"]["Rules"]
            if rules:
                encryption = rules[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
        except Exception:
            encryption = ""

        # Public access block
        pab_block = ""
        try:
            pab = s3.get_public_access_block(Bucket=name)
            pab_block = str(pab.get("PublicAccessBlockConfiguration", {}))
        except Exception:
            pab_block = ""

        rows.append({
            "account_id": account_id,
            "bucket_name": name,
            "region": region,
            "creation_date": create_str,
            "versioning": versioning_status,
            "default_encryption": encryption,
            "public_access_block": pab_block,
        })

    fieldnames = [
        "account_id",
        "bucket_name",
        "region",
        "creation_date",
        "versioning",
        "default_encryption",
        "public_access_block",
    ]

    print(f"[S3] Writing {len(rows)} buckets to {S3_BUCKETS_CSV} ...")
    with open(S3_BUCKETS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= S3: Storage Metrics =========

def export_s3_storage_metrics(session, account_id: str):
    """
    S3 storage metrics (BucketSizeBytes / NumberOfObjects) are reported
    to CloudWatch in us-east-1 per bucket & storage class.
    """
    start_time, end_time = get_time_range(DAYS_BACK)

    s3 = session.client("s3")
    cloudwatch = session.client("cloudwatch", region_name="us-east-1")

    rows = []

    print("[Metrics] Processing S3 storage metrics ...")
    resp = s3.list_buckets()
    buckets = resp.get("Buckets", [])

    for b in buckets:
        name = b["Name"]
        print(f"  [Metrics] Bucket {name}")
        dims_base = [{"Name": "BucketName", "Value": name}]

        # StorageType is required; we'll use "StandardStorage" and "AllStorageTypes" etc
        storage_types = ["StandardStorage", "StandardIAStorage", "OneZoneIAStorage", "IntelligentTieringFAStorage",
                         "IntelligentTieringIAStorage", "GlacierStorage", "DeepArchiveStorage", "AllStorageTypes"]

        for st in storage_types:
            dims = dims_base + [{"Name": "StorageType", "Value": st}]

            size_points = fetch_metric(
                cloudwatch,
                "AWS/S3",
                "BucketSizeBytes",
                dims,
                start_time,
                end_time,
                DAILY_PERIOD_SECONDS,
                ["Average"],
            )
            obj_points = fetch_metric(
                cloudwatch,
                "AWS/S3",
                "NumberOfObjects",
                dims,
                start_time,
                end_time,
                DAILY_PERIOD_SECONDS,
                ["Average"],
            )

            ts_map: dict[datetime, dict] = {}

            for p in size_points:
                ts = p["Timestamp"]
                entry = ts_map.setdefault(ts, {})
                if "Average" in p:
                    entry["bucket_size_bytes_avg"] = p["Average"]

            for p in obj_points:
                ts = p["Timestamp"]
                entry = ts_map.setdefault(ts, {})
                if "Average" in p:
                    entry["number_of_objects_avg"] = p["Average"]

            for ts, metrics in ts_map.items():
                rows.append({
                    "account_id": account_id,
                    "bucket_name": name,
                    "storage_type": st,
                    "timestamp": ts.isoformat(),
                    "bucket_size_bytes_avg": metrics.get("bucket_size_bytes_avg"),
                    "number_of_objects_avg": metrics.get("number_of_objects_avg"),
                    "period_seconds": DAILY_PERIOD_SECONDS,
                })

    fieldnames = [
        "account_id",
        "bucket_name",
        "storage_type",
        "timestamp",
        "bucket_size_bytes_avg",
        "number_of_objects_avg",
        "period_seconds",
    ]

    print(f"[Metrics] Writing {len(rows)} rows to {S3_STORAGE_CSV} ...")
    with open(S3_STORAGE_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= ELBv2 (ALB/NLB): Inventory =========

def export_elbv2_load_balancers(session, account_id: str, regions: list[str]):
    rows = []

    for region in regions:
        print(f"[ELBv2] Scanning region {region} ...")
        elbv2 = session.client("elbv2", region_name=region)

        paginator = elbv2.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for lb in page.get("LoadBalancers", []):
                lb_arn = lb["LoadBalancerArn"]
                lb_name = lb["LoadBalancerName"]
                lb_type = lb["Type"]
                scheme = lb.get("Scheme")
                ip_type = lb.get("IpAddressType")
                state = lb.get("State", {}).get("Code")
                vpc_id = lb.get("VpcId")
                created_time = lb.get("CreatedTime")
                azs = ";".join(a.get("ZoneName") for a in lb.get("AvailabilityZones", []))

                tags = []
                try:
                    tag_desc = elbv2.describe_tags(ResourceArns=[lb_arn])
                    for td in tag_desc.get("TagDescriptions", []):
                        if td.get("ResourceArn") == lb_arn:
                            tags = td.get("Tags", [])
                except Exception:
                    pass

                tag_str = ";".join(f"{t.get('Key','')}={t.get('Value','')}" for t in tags)

                rows.append({
                    "account_id": account_id,
                    "region": region,
                    "load_balancer_arn": lb_arn,
                    "load_balancer_name": lb_name,
                    "type": lb_type,
                    "scheme": scheme,
                    "ip_address_type": ip_type,
                    "state": state,
                    "vpc_id": vpc_id,
                    "availability_zones": azs,
                    "created_time": created_time.isoformat() if created_time else "",
                    "tags": tag_str,
                })

    fieldnames = [
        "account_id",
        "region",
        "load_balancer_arn",
        "load_balancer_name",
        "type",
        "scheme",
        "ip_address_type",
        "state",
        "vpc_id",
        "availability_zones",
        "created_time",
        "tags",
    ]

    print(f"[ELBv2] Writing {len(rows)} load balancers to {ELB_CSV} ...")
    with open(ELB_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= ELBv2: Metrics =========

def export_elbv2_metrics(session, account_id: str, regions: list[str]):
    start_time, end_time = get_time_range(DAYS_BACK)
    rows = []

    for region in regions:
        print(f"[Metrics] Processing ELBv2 metrics in region {region} ...")
        elbv2 = session.client("elbv2", region_name=region)
        cloudwatch = session.client("cloudwatch", region_name=region)

        lb_arns = []
        paginator = elbv2.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for lb in page.get("LoadBalancers", []):
                lb_arns.append(lb["LoadBalancerArn"])

        if not lb_arns:
            continue

        for lb_arn in lb_arns:
            # CloudWatch dimensions use the final part of ARN: app/xxx/yyy...
            lb_name_dim = lb_arn.split("loadbalancer/")[-1]
            print(f"  [Metrics] ELBv2 {lb_name_dim}")
            dims = [{"Name": "LoadBalancer", "Value": lb_name_dim}]

            metrics_to_fetch = {
                ("AWS/ApplicationELB", "RequestCount"): "request_count",
                ("AWS/ApplicationELB", "HTTPCode_ELB_4XX_Count"): "elb_4xx",
                ("AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count"): "elb_5xx",
                ("AWS/ApplicationELB", "TargetResponseTime"): "target_resp_time",
                ("AWS/NetworkELB", "ProcessedBytes"): "processed_bytes",
            }

            ts_map: dict[datetime, dict] = {}

            for (ns, metric_name), key in metrics_to_fetch.items():
                points = fetch_metric(
                    cloudwatch,
                    ns,
                    metric_name,
                    dims,
                    start_time,
                    end_time,
                    DEFAULT_PERIOD_SECONDS,
                    ["Sum"] if "Count" in metric_name or "Bytes" in metric_name else ["Average"],
                )
                for p in points:
                    ts = p["Timestamp"]
                    entry = ts_map.setdefault(ts, {})
                    stat_key = "Sum" if "Sum" in p else "Average"
                    entry[f"{key}_{stat_key.lower()}"] = p[stat_key]

            for ts, metrics in ts_map.items():
                rows.append({
                    "account_id": account_id,
                    "region": region,
                    "load_balancer": lb_name_dim,
                    "timestamp": ts.isoformat(),
                    "request_count_sum": metrics.get("request_count_sum"),
                    "elb_4xx_sum": metrics.get("elb_4xx_sum"),
                    "elb_5xx_sum": metrics.get("elb_5xx_sum"),
                    "target_response_time_avg": metrics.get("target_resp_time_average"),
                    "processed_bytes_sum": metrics.get("processed_bytes_sum"),
                    "period_seconds": DEFAULT_PERIOD_SECONDS,
                })

    fieldnames = [
        "account_id",
        "region",
        "load_balancer",
        "timestamp",
        "request_count_sum",
        "elb_4xx_sum",
        "elb_5xx_sum",
        "target_response_time_avg",
        "processed_bytes_sum",
        "period_seconds",
    ]

    print(f"[Metrics] Writing {len(rows)} rows to {ELB_METRICS_CSV} ...")
    with open(ELB_METRICS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= Lambda: Inventory =========

def export_lambda_functions(session, account_id: str, regions: list[str]):
    rows = []

    for region in regions:
        print(f"[Lambda] Scanning region {region} ...")
        lmb = session.client("lambda", region_name=region)

        paginator = lmb.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                fn_arn = fn["FunctionArn"]
                name = fn["FunctionName"]
                runtime = fn.get("Runtime")
                mem = fn.get("MemorySize")
                timeout = fn.get("Timeout")
                handler = fn.get("Handler")
                last_modified = fn.get("LastModified")
                code_size = fn.get("CodeSize")
                desc = fn.get("Description", "")

                # VPC
                vpc_cfg = fn.get("VpcConfig", {})
                subnet_ids = ";".join(vpc_cfg.get("SubnetIds", []))
                sg_ids = ";".join(vpc_cfg.get("SecurityGroupIds", []))

                # Tags
                tags = {}
                try:
                    tag_resp = lmb.list_tags(Resource=fn_arn)
                    tags = tag_resp.get("Tags", {})
                except Exception:
                    pass
                tag_str = ";".join(f"{k}={v}" for k, v in tags.items())

                rows.append({
                    "account_id": account_id,
                    "region": region,
                    "function_name": name,
                    "function_arn": fn_arn,
                    "runtime": runtime,
                    "memory_size": mem,
                    "timeout": timeout,
                    "handler": handler,
                    "last_modified": last_modified,
                    "code_size": code_size,
                    "description": desc,
                    "vpc_subnet_ids": subnet_ids,
                    "vpc_security_group_ids": sg_ids,
                    "tags": tag_str,
                })

    fieldnames = [
        "account_id",
        "region",
        "function_name",
        "function_arn",
        "runtime",
        "memory_size",
        "timeout",
        "handler",
        "last_modified",
        "code_size",
        "description",
        "vpc_subnet_ids",
        "vpc_security_group_ids",
        "tags",
    ]

    print(f"[Lambda] Writing {len(rows)} functions to {LAMBDA_FUNCTIONS_CSV} ...")
    with open(LAMBDA_FUNCTIONS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= Lambda: Metrics =========

def export_lambda_metrics(session, account_id: str, regions: list[str]):
    start_time, end_time = get_time_range(DAYS_BACK)
    rows = []

    for region in regions:
        print(f"[Metrics] Processing Lambda metrics in region {region} ...")
        lmb = session.client("lambda", region_name=region)
        cloudwatch = session.client("cloudwatch", region_name=region)

        fn_names = []
        paginator = lmb.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                fn_names.append(fn["FunctionName"])

        if not fn_names:
            continue

        for name in fn_names:
            print(f"  [Metrics] Lambda {name}")
            dims = [{"Name": "FunctionName", "Value": name}]

            metrics_sum = {
                "Invocations": "invocations",
                "Errors": "errors",
                "Throttles": "throttles",
            }
            metrics_avg = {
                "Duration": "duration",
            }

            ts_map: dict[datetime, dict] = {}

            for metric_name, key in metrics_sum.items():
                points = fetch_metric(
                    cloudwatch,
                    "AWS/Lambda",
                    metric_name,
                    dims,
                    start_time,
                    end_time,
                    DEFAULT_PERIOD_SECONDS,
                    ["Sum"],
                )
                for p in points:
                    ts = p["Timestamp"]
                    entry = ts_map.setdefault(ts, {})
                    if "Sum" in p:
                        entry[f"{key}_sum"] = p["Sum"]

            for metric_name, key in metrics_avg.items():
                points = fetch_metric(
                    cloudwatch,
                    "AWS/Lambda",
                    metric_name,
                    dims,
                    start_time,
                    end_time,
                    DEFAULT_PERIOD_SECONDS,
                    ["Average"],
                )
                for p in points:
                    ts = p["Timestamp"]
                    entry = ts_map.setdefault(ts, {})
                    if "Average" in p:
                        entry[f"{key}_avg"] = p["Average"]

            for ts, metrics in ts_map.items():
                rows.append({
                    "account_id": account_id,
                    "region": region,
                    "function_name": name,
                    "timestamp": ts.isoformat(),
                    "invocations_sum": metrics.get("invocations_sum"),
                    "errors_sum": metrics.get("errors_sum"),
                    "throttles_sum": metrics.get("throttles_sum"),
                    "duration_avg_ms": metrics.get("duration_avg"),
                    "period_seconds": DEFAULT_PERIOD_SECONDS,
                })

    fieldnames = [
        "account_id",
        "region",
        "function_name",
        "timestamp",
        "invocations_sum",
        "errors_sum",
        "throttles_sum",
        "duration_avg_ms",
        "period_seconds",
    ]

    print(f"[Metrics] Writing {len(rows)} rows to {LAMBDA_METRICS_CSV} ...")
    with open(LAMBDA_METRICS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= Cost Explorer =========

def _ce_paginated(ce, params: dict):
    """Small helper to handle Cost Explorer pagination."""
    next_token = None
    while True:
        effective = dict(params)
        if next_token:
            effective["NextPageToken"] = next_token
        resp = ce.get_cost_and_usage(**effective)
        yield resp
        next_token = resp.get("NextPageToken")
        if not next_token:
            break


def export_daily_cost_by_service(session, account_id: str):
    ce = session.client("ce")

    start_date, end_date = get_date_range_for_cost(DAYS_BACK)
    print(f"[Cost] Fetching DAILY cost by SERVICE from {start_date} to {end_date} ...")

    rows = []

    base_params = {
        "TimePeriod": {"Start": start_date, "End": end_date},
        "Granularity": "DAILY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ],
    }

    for resp in _ce_paginated(ce, base_params):
        for result in resp.get("ResultsByTime", []):
            date_str = result["TimePeriod"]["Start"]
            for group in result.get("Groups", []):
                service_name = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                unit = group["Metrics"]["UnblendedCost"]["Unit"]

                rows.append({
                    "account_id": account_id,
                    "date": date_str,
                    "service_name": service_name,
                    "cost_amount": amount,
                    "currency": unit,
                })

    fieldnames = [
        "account_id",
        "date",
        "service_name",
        "cost_amount",
        "currency",
    ]

    print(f"[Cost] Writing {len(rows)} rows to {DAILY_COST_CSV} ...")
    with open(DAILY_COST_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_daily_cost_by_service_region(session, account_id: str):
    ce = session.client("ce")

    start_date, end_date = get_date_range_for_cost(DAYS_BACK)
    print(f"[Cost] Fetching DAILY cost by SERVICE & REGION from {start_date} to {end_date} ...")

    rows = []

    base_params = {
        "TimePeriod": {"Start": start_date, "End": end_date},
        "Granularity": "DAILY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "DIMENSION", "Key": "REGION"},
        ],
    }

    for resp in _ce_paginated(ce, base_params):
        for result in resp.get("ResultsByTime", []):
            date_str = result["TimePeriod"]["Start"]
            for group in result.get("Groups", []):
                service_name, region = group["Keys"]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                unit = group["Metrics"]["UnblendedCost"]["Unit"]

                rows.append({
                    "account_id": account_id,
                    "date": date_str,
                    "service_name": service_name,
                    "region": region,
                    "cost_amount": amount,
                    "currency": unit,
                })

    fieldnames = [
        "account_id",
        "date",
        "service_name",
        "region",
        "cost_amount",
        "currency",
    ]

    print(f"[Cost] Writing {len(rows)} rows to {DAILY_COST_REGION_CSV} ...")
    with open(DAILY_COST_REGION_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_daily_cost_by_tag_environment(session, account_id: str):
    """
    Example: cost by TAG:Environment
    Make sure you actually use tag 'Environment' (Prod/Dev/Test).
    """
    ce = session.client("ce")

    start_date, end_date = get_date_range_for_cost(DAYS_BACK)
    print(f"[Cost] Fetching DAILY cost by TAG:Environment from {start_date} to {end_date} ...")

    rows = []

    base_params = {
        "TimePeriod": {"Start": start_date, "End": end_date},
        "Granularity": "DAILY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [
            {"Type": "TAG", "Key": "Environment"},
        ],
    }

    for resp in _ce_paginated(ce, base_params):
        for result in resp.get("ResultsByTime", []):
            date_str = result["TimePeriod"]["Start"]
            for group in result.get("Groups", []):
                tag_val = group["Keys"][0]  # e.g. "Environment$Prod"
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                unit = group["Metrics"]["UnblendedCost"]["Unit"]

                rows.append({
                    "account_id": account_id,
                    "date": date_str,
                    "tag_environment": tag_val,
                    "cost_amount": amount,
                    "currency": unit,
                })

    fieldnames = [
        "account_id",
        "date",
        "tag_environment",
        "cost_amount",
        "currency",
    ]

    print(f"[Cost] Writing {len(rows)} rows to {DAILY_COST_TAG_ENV_CSV} ...")
    with open(DAILY_COST_TAG_ENV_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= Main =========

def main():
    session = boto3.Session()
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    account_id = identity["Account"]

    print(f"Using AWS Account: {account_id}")

    # Global EC2 to get regions
    ec2_global = session.client("ec2")
    regions_resp = ec2_global.describe_regions(AllRegions=False)
    regions = [r["RegionName"] for r in regions_resp["Regions"]]

    print(f"Regions: {regions}")

    # 1) EC2 inventory + metrics
    export_ec2_instances(session, account_id, regions)
    export_ec2_metrics(session, account_id, regions)

    # 2) EBS inventory + metrics
    export_ebs_volumes(session, account_id, regions)
    export_ebs_metrics(session, account_id, regions)

    # 3) RDS inventory + metrics
    export_rds_instances(session, account_id, regions)
    export_rds_metrics(session, account_id, regions)

    # 4) S3 buckets + storage metrics
    export_s3_buckets(session, account_id)
    export_s3_storage_metrics(session, account_id)

    # 5) ELBv2 (ALB/NLB) inventory + metrics
    export_elbv2_load_balancers(session, account_id, regions)
    export_elbv2_metrics(session, account_id, regions)

    # 6) Lambda inventory + metrics
    export_lambda_functions(session, account_id, regions)
    export_lambda_metrics(session, account_id, regions)

    # 7) Cost Explorer (multiple breakdowns)
    export_daily_cost_by_service(session, account_id)
    export_daily_cost_by_service_region(session, account_id)
    export_daily_cost_by_tag_environment(session, account_id)

    print("\nDone. CSV files generated:")
    print(f"  - {EC2_INSTANCES_CSV}")
    print(f"  - {EC2_METRICS_CSV}")
    print(f"  - {EBS_VOLUMES_CSV}")
    print(f"  - {EBS_METRICS_CSV}")
    print(f"  - {RDS_INSTANCES_CSV}")
    print(f"  - {RDS_METRICS_CSV}")
    print(f"  - {S3_BUCKETS_CSV}")
    print(f"  - {S3_STORAGE_CSV}")
    print(f"  - {ELB_CSV}")
    print(f"  - {ELB_METRICS_CSV}")
    print(f"  - {LAMBDA_FUNCTIONS_CSV}")
    print(f"  - {LAMBDA_METRICS_CSV}")
    print(f"  - {DAILY_COST_CSV}")
    print(f"  - {DAILY_COST_REGION_CSV}")
    print(f"  - {DAILY_COST_TAG_ENV_CSV}")


if __name__ == "__main__":
    main()
