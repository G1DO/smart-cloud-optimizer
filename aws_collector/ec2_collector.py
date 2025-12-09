"""
EC2 Inventory Collector
Collects EC2 instances, EBS volumes, and regions information
"""
import csv
from pathlib import Path
from typing import Dict, List

from .config import AWSConfig, DATA_DIR


class EC2Collector:
    """Collects EC2 inventory data"""
    
    def __init__(self, config: AWSConfig):
        """
        Initialize EC2 Collector
        
        Args:
            config: AWSConfig instance
        """
        self.config = config
        self.account_id = config.account_id
        self.regions = config.regions
    
    def list_instances(self) -> List[Dict]:
        """
        List all EC2 instances across all regions
        
        Returns:
            List of instance dictionaries
        """
        from datetime import datetime
        
        all_instances = []
        total_regions = len(self.regions)
        
        print("\n[Inventory] Collecting EC2 instances...")
        print(f"  Total regions to scan: {total_regions}")
        start_time = datetime.now()
        
        for idx, region in enumerate(self.regions, 1):
            try:
                ec2 = self.config.get_ec2_client(region)
                region_start = datetime.now()
                print(f"  [{idx}/{total_regions}] Scanning region {region}...", end="", flush=True)
                
                region_count = 0
                # Include all instance states (running, stopped, terminated) for historical data
                paginator = ec2.get_paginator('describe_instances')
                for page in paginator.paginate():
                    for reservation in page.get('Reservations', []):
                        for inst in reservation.get('Instances', []):
                            region_count += 1
                            instance_data = {
                                'account_id': self.account_id,
                                'region': region,
                                'instance_id': inst['InstanceId'],
                                'instance_type': inst.get('InstanceType', ''),
                                'state': inst.get('State', {}).get('Name', ''),
                                'availability_zone': inst.get('Placement', {}).get('AvailabilityZone', ''),
                                'launch_time': inst.get('LaunchTime').isoformat() if inst.get('LaunchTime') else None,
                                'private_ip': inst.get('PrivateIpAddress'),
                                'public_ip': inst.get('PublicIpAddress'),
                                'vpc_id': inst.get('VpcId'),
                                'subnet_id': inst.get('SubnetId'),
                                'ami_id': inst.get('ImageId'),
                                'architecture': inst.get('Architecture'),
                                'monitoring': inst.get('Monitoring', {}).get('State'),
                                'cpu_cores': inst.get('CpuOptions', {}).get('CoreCount'),
                                'threads_per_core': inst.get('CpuOptions', {}).get('ThreadsPerCore'),
                                'tags': {tag['Key']: tag['Value'] for tag in inst.get('Tags', [])},
                            }
                            all_instances.append(instance_data)
                
                elapsed = (datetime.now() - region_start).total_seconds()
                print(f" ✓ Found {region_count} instances ({elapsed:.1f}s)")
            except Exception as e:
                print(f" ✗ ERROR: {e}")
        
        total_time = (datetime.now() - start_time).total_seconds()
        print(f"\n[Inventory] ✓ Completed: Found {len(all_instances)} EC2 instances in {total_time:.1f}s")
        return all_instances
    
    def list_volumes(self) -> List[Dict]:
        """
        List all EBS volumes across all regions
        
        Returns:
            List of volume dictionaries
        """
        from datetime import datetime
        
        all_volumes = []
        total_regions = len(self.regions)
        
        print("\n[Inventory] Collecting EBS volumes...")
        print(f"  Total regions to scan: {total_regions}")
        start_time = datetime.now()
        
        for idx, region in enumerate(self.regions, 1):
            try:
                ec2 = self.config.get_ec2_client(region)
                region_start = datetime.now()
                print(f"  [{idx}/{total_regions}] Scanning region {region}...", end="", flush=True)
                
                region_count = 0
                # Include all volume states for historical data
                paginator = ec2.get_paginator('describe_volumes')
                for page in paginator.paginate():
                    for vol in page.get('Volumes', []):
                        region_count += 1
                        volume_data = {
                            'account_id': self.account_id,
                            'region': region,
                            'volume_id': vol['VolumeId'],
                            'size_gb': vol.get('Size'),
                            'volume_type': vol.get('VolumeType'),
                            'iops': vol.get('Iops'),
                            'throughput': vol.get('Throughput'),
                            'encrypted': vol.get('Encrypted'),
                            'state': vol.get('State'),
                            'availability_zone': vol.get('AvailabilityZone'),
                            'create_time': vol.get('CreateTime').isoformat() if vol.get('CreateTime') else None,
                            'snapshot_id': vol.get('SnapshotId'),
                            'attachments': [
                                {
                                    'instance_id': att.get('InstanceId'),
                                    'device': att.get('Device'),
                                    'state': att.get('State')
                                }
                                for att in vol.get('Attachments', [])
                            ],
                            'tags': {tag['Key']: tag['Value'] for tag in vol.get('Tags', [])},
                            }
                        all_volumes.append(volume_data)
                
                elapsed = (datetime.now() - region_start).total_seconds()
                print(f" ✓ Found {region_count} volumes ({elapsed:.1f}s)")
            except Exception as e:
                print(f" ✗ ERROR: {e}")
        
        total_time = (datetime.now() - start_time).total_seconds()
        print(f"\n[Inventory] ✓ Completed: Found {len(all_volumes)} EBS volumes in {total_time:.1f}s")
        return all_volumes
    
    def list_regions(self) -> List[Dict]:
        """
        List all available AWS regions
        
        Returns:
            List of region dictionaries
        """
        regions_data = []
        
        print("\n[Inventory] Collecting regions...")
        
        try:
            ec2_global = self.config.ec2
            response = ec2_global.describe_regions(AllRegions=False)
            
            for region in response.get('Regions', []):
                region_data = {
                    'region_name': region['RegionName'],
                    'endpoint': region.get('OptInStatus', 'opt-in-not-required'),
                }
                regions_data.append(region_data)
            
            print(f"[Inventory] Found {len(regions_data)} regions")
        except Exception as e:
            print(f"[WARN] Failed to get regions: {e}")
        
        return regions_data
    
    def save_inventory(self):
        """Collect and save all inventory data as CSV"""
        inventory_dir = DATA_DIR / "inventory"
        inventory_dir.mkdir(parents=True, exist_ok=True)
        
        # Collect instances
        instances = self.list_instances()
        instances_file = inventory_dir / "instances_consolidated.csv"
        
        if instances:
            fieldnames = list(instances[0].keys())
            with open(instances_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(instances)
            print(f"[Inventory] ✓ Saved {len(instances)} instances to {instances_file.name}")
        else:
            # Create empty CSV with standard fields
            fieldnames = [
                'account_id', 'region', 'instance_id', 'instance_type', 'state',
                'availability_zone', 'launch_time', 'private_ip', 'public_ip',
                'vpc_id', 'subnet_id', 'ami_id', 'tenancy', 'hypervisor',
                'architecture', 'monitoring', 'cpu_cores', 'threads_per_core',
                'tags'
            ]
            with open(instances_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            print(f"[Inventory] ✓ Created empty {instances_file.name}")
        
        # Collect volumes
        volumes = self.list_volumes()
        volumes_file = inventory_dir / "volumes_consolidated.csv"
        
        if volumes:
            # Flatten nested structures
            flattened_volumes = []
            for vol in volumes:
                flat_vol = {}
                for key, value in vol.items():
                    if key == 'tags' and isinstance(value, dict):
                        flat_vol[key] = ';'.join(f"{k}={v}" for k, v in value.items())
                    elif key == 'attachments' and isinstance(value, list):
                        flat_vol[key] = ';'.join(
                            f"{a.get('instance_id', '')}:{a.get('device', '')}" 
                            for a in value if isinstance(a, dict)
                        )
                    else:
                        flat_vol[key] = value
                flattened_volumes.append(flat_vol)
            
            fieldnames = list(flattened_volumes[0].keys())
            with open(volumes_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(flattened_volumes)
            print(f"[Inventory] ✓ Saved {len(volumes)} volumes to {volumes_file.name}")
        else:
            # Create empty CSV with standard fields
            fieldnames = [
                'account_id', 'region', 'volume_id', 'size_gb', 'volume_type',
                'iops', 'throughput', 'encrypted', 'state', 'availability_zone',
                'snapshot_id', 'create_time', 'attachments', 'tags'
            ]
            with open(volumes_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            print(f"[Inventory] ✓ Created empty {volumes_file.name}")
        
        # Collect regions
        regions = self.list_regions()
        regions_file = inventory_dir / "regions_consolidated.csv"
        
        if regions:
            fieldnames = list(regions[0].keys())
            with open(regions_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(regions)
            print(f"[Inventory] ✓ Saved {len(regions)} regions to {regions_file.name}")
        else:
            fieldnames = ['region_name', 'endpoint']
            with open(regions_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            print(f"[Inventory] ✓ Created empty {regions_file.name}")
        
        return {
            'instances': instances_file,
            'volumes': volumes_file,
            'regions': regions_file
        }

