import boto3
import csv
from datetime import datetime, timedelta, timezone

# ========= إعدادات عامة =========

# عدد الأيام اللي عايزها (5 شهور تقريبا ~ 150 يوم)
DAYS_BACK = 150

# فترة الـ CloudWatch metrics (بالثواني) - هنا كل ساعة
PERIOD_SECONDS = 10800

# أسماء ملفات الـ CSV الناتجة
EC2_INSTANCES_CSV = "ec2_instances.csv"
EC2_METRICS_CSV = "ec2_metrics.csv"
DAILY_COST_CSV = "daily_cost_by_service.csv"


# ========= دوال مساعدة للوقت =========

def get_time_range(days_back: int):
    """ترجع start_time و end_time للـ CloudWatch."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    return start, end


def get_date_range_for_cost(days_back: int):
    """ترجع start_date و end_date للـ Cost Explorer."""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days_back)
    # Cost Explorer يتعامل مع تاريخ بدون وقت، end غير شامل
    return start_date.isoformat(), end_date.isoformat()


# ========= EC2: Inventory =========

def export_ec2_instances(ec2_client, account_id: str, regions: list[str]):
    """يجيب كل EC2 instances في كل regions ويخزنها في CSV."""
    rows = []

    for region in regions:
        print(f"[EC2] Scanning region {region} ...")
        regional_ec2 = boto3.client("ec2", region_name=region)

        paginator = regional_ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    instance_id = inst["InstanceId"]
                    instance_type = inst.get("InstanceType", "")
                    state = inst.get("State", {}).get("Name", "")
                    launch_time = inst.get("LaunchTime")
                    az = inst.get("Placement", {}).get("AvailabilityZone", "")

                    # tags → نخليها نص بسيط "Key=Value;Key2=Value2"
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
        "tags",
    ]

    print(f"[EC2] Writing {len(rows)} instances to {EC2_INSTANCES_CSV} ...")
    with open(EC2_INSTANCES_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= CloudWatch Metrics Helper =========

def fetch_metric(cloudwatch_client, namespace: str, metric_name: str,
                 dimensions: list[dict], start_time, end_time, period: int,
                 statistics: list[str]):
    """دالة عامة تجيب metric واحدة من CloudWatch."""
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


# ========= EC2: Metrics =========

def export_ec2_metrics(account_id: str, regions: list[str]):
    """يجيب CPU / Network / Disk metrics لكل EC2 instance ويخزنها في CSV."""
    start_time, end_time = get_time_range(DAYS_BACK)

    rows = []

    for region in regions:
        print(f"[Metrics] Processing EC2 metrics in region {region} ...")
        ec2 = boto3.client("ec2", region_name=region)
        cloudwatch = boto3.client("cloudwatch", region_name=region)

        # نجيب الـ instances في الريجون ده
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
            print(f"  [Metrics] Instance {instance_id}")

            dims = [{"Name": "InstanceId", "Value": instance_id}]

            cpu_points = fetch_metric(
                cloudwatch,
                namespace="AWS/EC2",
                metric_name="CPUUtilization",
                dimensions=dims,
                start_time=start_time,
                end_time=end_time,
                period=PERIOD_SECONDS,
                statistics=["Average", "Maximum"],
            )

            net_in_points = fetch_metric(
                cloudwatch,
                namespace="AWS/EC2",
                metric_name="NetworkIn",
                dimensions=dims,
                start_time=start_time,
                end_time=end_time,
                period=PERIOD_SECONDS,
                statistics=["Average"],
            )

            net_out_points = fetch_metric(
                cloudwatch,
                namespace="AWS/EC2",
                metric_name="NetworkOut",
                dimensions=dims,
                start_time=start_time,
                end_time=end_time,
                period=PERIOD_SECONDS,
                statistics=["Average"],
            )

            disk_read_points = fetch_metric(
                cloudwatch,
                namespace="AWS/EC2",
                metric_name="DiskReadOps",
                dimensions=dims,
                start_time=start_time,
                end_time=end_time,
                period=PERIOD_SECONDS,
                statistics=["Average"],
            )

            disk_write_points = fetch_metric(
                cloudwatch,
                namespace="AWS/EC2",
                metric_name="DiskWriteOps",
                dimensions=dims,
                start_time=start_time,
                end_time=end_time,
                period=PERIOD_SECONDS,
                statistics=["Average"],
            )

            # ندمجهم على مستوى الـ timestamp
            ts_map = {}

            def merge_points(points, key_prefix, has_max=False):
                for p in points:
                    ts = p["Timestamp"]
                    entry = ts_map.setdefault(ts, {})
                    if "Average" in p:
                        entry[f"{key_prefix}_avg"] = p["Average"]
                    if has_max and "Maximum" in p:
                        entry[f"{key_prefix}_max"] = p["Maximum"]

            merge_points(cpu_points, "cpu", has_max=True)
            merge_points(net_in_points, "network_in", has_max=False)
            merge_points(net_out_points, "network_out", has_max=False)
            merge_points(disk_read_points, "disk_read_ops", has_max=False)
            merge_points(disk_write_points, "disk_write_ops", has_max=False)

            for ts, metrics in ts_map.items():
                row = {
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
                    "period_seconds": PERIOD_SECONDS,
                }
                rows.append(row)

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
        "period_seconds",
    ]

    print(f"[Metrics] Writing {len(rows)} rows to {EC2_METRICS_CSV} ...")
    with open(EC2_METRICS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ========= Cost Explorer =========

def export_daily_cost_by_service(account_id: str):
    """يجيب daily cost per service آخر 5 شهور من Cost Explorer ويخزنها في CSV."""
    ce = boto3.client("ce")  # Cost Explorer ملوش region مهم

    start_date, end_date = get_date_range_for_cost(DAYS_BACK)
    print(f"[Cost] Fetching cost from {start_date} to {end_date} ...")

    rows = []
    next_token = None

    while True:
        params = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [
                {"Type": "DIMENSION", "Key": "SERVICE"},
            ],
        }
        if next_token:
            params["NextPageToken"] = next_token

        response = ce.get_cost_and_usage(**params)

        for result in response.get("ResultsByTime", []):
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

        next_token = response.get("NextPageToken")
        if not next_token:
            break

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


# ========= Main =========

def main():
    session = boto3.Session()
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    account_id = identity["Account"]

    print(f"Using AWS Account: {account_id}")

    # نجيب كل regions المتاحة
    ec2_global = session.client("ec2")
    regions_resp = ec2_global.describe_regions(AllRegions=False)
    regions = [r["RegionName"] for r in regions_resp["Regions"]]

    print(f"Regions: {regions}")

    # 1) EC2 inventory
    export_ec2_instances(ec2_global, account_id, regions)

    # 2) EC2 metrics
    export_ec2_metrics(account_id, regions)

    # 3) Daily cost per service
    export_daily_cost_by_service(account_id)

    print("Done. CSV files generated:")
    print(f"  - {EC2_INSTANCES_CSV}")
    print(f"  - {EC2_METRICS_CSV}")
    print(f"  - {DAILY_COST_CSV}")


if __name__ == "__main__":
    main()
