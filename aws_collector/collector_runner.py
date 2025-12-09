"""
Main Collector Runner
Orchestrates month-by-month data collection for the last 5 months
"""
from typing import List, Dict
from datetime import datetime
import sys

from .config import AWSConfig, init_config
from .date_utils import get_last_n_months, get_month_key
from .cost_collector import CostCollector
from .cw_collector import CloudWatchCollector
from .pricing_collector import PricingCollector
from .ec2_collector import EC2Collector


class CollectorRunner:
    """Main runner that orchestrates all data collection"""
    
    def __init__(self, config: AWSConfig = None):
        """
        Initialize Collector Runner
        
        Args:
            config: AWSConfig instance (creates default if None)
        """
        self.config = config or init_config()
        
        # Initialize collectors
        self.cost_collector = CostCollector(self.config)
        self.cw_collector = CloudWatchCollector(self.config)
        self.pricing_collector = PricingCollector(self.config)
        self.ec2_collector = EC2Collector(self.config)
    
    def _load_previous_inventory(self):
        """Load inventory from previous collection if available"""
        import json
        from pathlib import Path
        from .config import DATA_DIR
        
        inventory_file = DATA_DIR / "inventory" / "instances.json"
        if inventory_file.exists():
            try:
                with open(inventory_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"  [INFO] Could not load previous inventory: {e}")
        return None
    
    def collect_metrics_for_month(
        self,
        start_date: str,
        end_date: str,
        month_key: str
    ):
        """
        Collect CloudWatch metrics for a specific month
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            month_key: Month key (YYYY-MM)
        """
        print(f"\n[Metrics] Collecting metrics for {month_key}...")
        metrics_start = datetime.now()
        
        # Get current inventory
        instances = self.ec2_collector.list_instances()
        volumes = self.ec2_collector.list_volumes()
        
        # Also try to load previous inventory to catch terminated instances
        previous_instances = self._load_previous_inventory()
        if previous_instances:
            # Merge with current instances, prioritizing current ones
            current_ids = {inst['instance_id'] for inst in instances}
            added_count = 0
            for prev_inst in previous_instances:
                if prev_inst['instance_id'] not in current_ids:
                    instances.append(prev_inst)
                    added_count += 1
            if added_count > 0:
                print(f"  [INFO] Added {added_count} instances from previous inventory for historical metrics")
        
        # Also try to load from old CSV inventory files
        import csv
        from pathlib import Path
        from .config import DATA_DIR
        
        old_csv_file = DATA_DIR / "inventory" / "ec2_instances.csv"
        if old_csv_file.exists():
            try:
                with open(old_csv_file, 'r') as f:
                    reader = csv.DictReader(f)
                    current_ids = {inst['instance_id'] for inst in instances}
                    csv_added = 0
                    for row in reader:
                        if row.get('instance_id') and row['instance_id'] not in current_ids:
                            # Convert CSV row to instance dict format
                            instance_dict = {
                                'account_id': row.get('account_id', ''),
                                'region': row.get('region', ''),
                                'instance_id': row['instance_id'],
                                'instance_type': row.get('instance_type', ''),
                                'state': row.get('state', 'terminated'),  # Assume terminated if in old CSV
                            }
                            instances.append(instance_dict)
                            csv_added += 1
                    if csv_added > 0:
                        print(f"  [INFO] Added {csv_added} instances from old CSV inventory for historical metrics")
            except Exception as e:
                print(f"  [WARN] Could not load old CSV inventory: {e}")
        
        # Collect EC2 metrics - include ALL instances (running, stopped, terminated)
        # CloudWatch keeps historical metrics for terminated instances
        all_instances = instances  # Use all instances for historical data collection
        total_ec2 = len(all_instances)
        running_count = len([i for i in instances if i['state'] == 'running'])
        terminated_count = len([i for i in instances if i['state'] == 'terminated'])
        print(f"\n  [EC2] Processing {total_ec2} instances (running: {running_count}, terminated: {terminated_count})...")
        print(f"  Note: Historical metrics available for terminated instances via CloudWatch")
        ec2_count = 0
        for idx, instance in enumerate(all_instances, 1):
            try:
                if idx % 10 == 0 or idx == total_ec2:
                    print(f"    Progress: {idx}/{total_ec2} ({idx*100//total_ec2 if total_ec2 > 0 else 0}%)", end="\r")
                    sys.stdout.flush()
                
                metrics = self.cw_collector.get_ec2_metrics(
                    instance['instance_id'],
                    instance['region'],
                    start_date,
                    end_date
                )
                self.cw_collector.save_csv(
                    metrics, 'ec2', month_key, instance['instance_id']
                )
                ec2_count += 1
            except Exception as e:
                print(f"\n    [WARN] Failed {instance['instance_id']}: {e}")
        
        print(f"\n  ✓ Collected EC2 metrics for {ec2_count}/{total_ec2} instances")
        if terminated_count > 0:
            print(f"  ℹ️  {terminated_count} terminated instances - historical metrics collected from CloudWatch")
        
        # Collect EBS metrics
        attached_volumes = [v for v in volumes if v['state'] == 'in-use']
        total_ebs = len(attached_volumes)
        print(f"\n  [EBS] Processing {total_ebs} attached volumes...")
        ebs_count = 0
        for idx, volume in enumerate(attached_volumes, 1):
            try:
                if idx % 10 == 0 or idx == total_ebs:
                    print(f"    Progress: {idx}/{total_ebs} ({idx*100//total_ebs if total_ebs > 0 else 0}%)", end="\r")
                    sys.stdout.flush()
                
                metrics = self.cw_collector.get_ebs_metrics(
                    volume['volume_id'],
                    volume['region'],
                    start_date,
                    end_date
                )
                self.cw_collector.save_csv(
                    metrics, 'ebs', month_key, volume['volume_id']
                )
                ebs_count += 1
            except Exception as e:
                print(f"\n    [WARN] Failed {volume['volume_id']}: {e}")
        
        print(f"\n  ✓ Collected EBS metrics for {ebs_count}/{total_ebs} volumes")
        
        # Collect Lambda metrics
        print(f"\n  [Lambda] Scanning {len(self.config.regions)} regions...")
        lambda_count = 0
        lambda_total = 0
        for region_idx, region in enumerate(self.config.regions, 1):
            try:
                print(f"    [{region_idx}/{len(self.config.regions)}] Region {region}...", end="", flush=True)
                lambda_client_list = self.config.get_lambda_client(region)
                paginator = lambda_client_list.get_paginator('list_functions')
                
                region_funcs = []
                for page in paginator.paginate():
                    region_funcs.extend(page.get('Functions', []))
                
                lambda_total += len(region_funcs)
                print(f" Found {len(region_funcs)} functions")
                
                for func in region_funcs:
                    try:
                        metrics = self.cw_collector.get_lambda_metrics(
                            func['FunctionName'],
                            region,
                            start_date,
                            end_date
                        )
                        self.cw_collector.save_csv(
                            metrics, 'lambda', month_key, func['FunctionName']
                        )
                        lambda_count += 1
                    except Exception as e:
                        print(f"      [WARN] Failed {func['FunctionName']}: {e}")
            except Exception as e:
                print(f" ✗ ERROR: {e}")
        
        print(f"  ✓ Collected Lambda metrics for {lambda_count}/{lambda_total} functions")
        
        # Collect RDS metrics
        print(f"\n  [RDS] Scanning {len(self.config.regions)} regions...")
        rds_count = 0
        rds_total = 0
        for region_idx, region in enumerate(self.config.regions, 1):
            try:
                print(f"    [{region_idx}/{len(self.config.regions)}] Region {region}...", end="", flush=True)
                rds_client = self.config.get_rds_client(region)
                paginator = rds_client.get_paginator('describe_db_instances')
                
                region_dbs = []
                for page in paginator.paginate():
                    region_dbs.extend(page.get('DBInstances', []))
                
                rds_total += len(region_dbs)
                print(f" Found {len(region_dbs)} instances")
                
                for db in region_dbs:
                    try:
                        metrics = self.cw_collector.get_rds_metrics(
                            db['DBInstanceIdentifier'],
                            region,
                            start_date,
                            end_date
                        )
                        self.cw_collector.save_csv(
                            metrics, 'rds', month_key, db['DBInstanceIdentifier']
                        )
                        rds_count += 1
                    except Exception as e:
                        print(f"      [WARN] Failed {db['DBInstanceIdentifier']}: {e}")
            except Exception as e:
                print(f" ✗ ERROR: {e}")
        
        print(f"  ✓ Collected RDS metrics for {rds_count}/{rds_total} instances")
        
        # Collect S3 metrics
        print(f"  Collecting S3 metrics...")
        s3_count = 0
        try:
            s3_client = self.config.s3
            buckets = s3_client.list_buckets().get('Buckets', [])
            
            for bucket in buckets:
                try:
                    metrics = self.cw_collector.get_s3_metrics(
                        bucket['Name'],
                        start_date,
                        end_date
                    )
                    self.cw_collector.save_csv(
                        metrics, 's3', month_key, bucket['Name']
                    )
                    s3_count += 1
                except Exception as e:
                    print(f"    [WARN] Failed to collect S3 metrics for {bucket['Name']}: {e}")
        except Exception as e:
            print(f"    [WARN] Failed to list S3 buckets: {e}")
        
        print(f"  ✓ Collected S3 metrics for {s3_count} buckets")
        
        metrics_time = (datetime.now() - metrics_start).total_seconds()
        print(f"\n[Metrics] ✓ Completed {month_key} in {metrics_time:.1f}s")
    
    def run(self, months: int = 5):
        """
        Run complete data collection for the last N months
        
        Args:
            months: Number of months to collect (default: 5)
        """
        overall_start = datetime.now()
        
        print("=" * 60)
        print("AWS Data Collector - Starting Collection")
        print("=" * 60)
        print(f"Account ID: {self.config.account_id}")
        print(f"Regions: {len(self.config.regions)}")
        print(f"Months to collect: {months}")
        print(f"Start time: {overall_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Get month ranges
        month_ranges = get_last_n_months(months)
        
        # Step 1: Collect inventory (once)
        print("\n" + "=" * 60)
        print("STEP 1: Collecting Inventory")
        print("=" * 60)
        inventory_start = datetime.now()
        inventory_files = self.ec2_collector.save_inventory()
        inventory_time = (datetime.now() - inventory_start).total_seconds()
        print(f"\n✓ Inventory collection completed in {inventory_time:.1f}s")
        
        # Step 2: Collect data for each month
        print("\n" + "=" * 60)
        print("STEP 2: Collecting Monthly Data")
        print("=" * 60)
        
        total_months = len(month_ranges)
        for month_idx, (start_date, end_date) in enumerate(month_ranges, 1):
            month_key = get_month_key(start_date)
            month_start = datetime.now()
            
            print(f"\n{'=' * 60}")
            print(f"Month {month_idx}/{total_months}: {month_key} ({start_date} to {end_date})")
            print(f"{'=' * 60}")
            
            # Collect cost data
            print(f"\n[{month_key}] Step 1/3: Collecting cost data...")
            cost_start = datetime.now()
            self.cost_collector.collect_month(start_date, end_date)
            cost_time = (datetime.now() - cost_start).total_seconds()
            print(f"[{month_key}] ✓ Cost data collected in {cost_time:.1f}s")
            
            # Collect metrics
            print(f"\n[{month_key}] Step 2/3: Collecting metrics...")
            self.collect_metrics_for_month(start_date, end_date, month_key)
            
            # Collect pricing snapshot
            print(f"\n[{month_key}] Step 3/3: Collecting pricing snapshot...")
            pricing_start = datetime.now()
            self.pricing_collector.collect_month_snapshot(month_key, regions=self.config.regions)
            pricing_time = (datetime.now() - pricing_start).total_seconds()
            print(f"[{month_key}] ✓ Pricing snapshot collected in {pricing_time:.1f}s")
            
            month_time = (datetime.now() - month_start).total_seconds()
            print(f"\n[{month_key}] ✓ Month completed in {month_time:.1f}s")
            
            # Show progress
            remaining_months = total_months - month_idx
            if remaining_months > 0:
                elapsed_total = (datetime.now() - overall_start).total_seconds()
                avg_time_per_month = elapsed_total / month_idx
                estimated_remaining = avg_time_per_month * remaining_months
                print(f"  Progress: {month_idx}/{total_months} months ({month_idx*100//total_months}%)")
                print(f"  Estimated time remaining: {estimated_remaining/60:.1f} minutes")
        
        overall_time = (datetime.now() - overall_start).total_seconds()
        
        print("\n" + "=" * 60)
        print("✓ Collection Complete!")
        print("=" * 60)
        print(f"Total time: {overall_time/60:.1f} minutes ({overall_time:.1f}s)")
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\nData saved to:")
        print("  - Cost data: data/cost/YYYY-MM/")
        print("  - Metrics: data/metrics/{service}/YYYY-MM/")
        print("  - Pricing: data/pricing/YYYY-MM.json")
        print("  - Inventory: data/inventory/")
        print("=" * 60)


def main():
    """Main entry point"""
    runner = CollectorRunner()
    runner.run(months=5)


if __name__ == "__main__":
    main()

