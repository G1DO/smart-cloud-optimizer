"""
Convert JSON inventory files to CSV
"""
import json
import csv
from pathlib import Path

from .config import DATA_DIR


def convert_json_to_csv():
    """Convert all JSON inventory files to CSV"""
    inventory_dir = DATA_DIR / "inventory"
    
    # Convert instances.json
    instances_json = inventory_dir / "instances.json"
    instances_csv = inventory_dir / "instances_consolidated.csv"
    
    if instances_json.exists():
        with open(instances_json, 'r') as f:
            data = json.load(f)
        
        if data and len(data) > 0:
            fieldnames = list(data[0].keys())
            with open(instances_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            print(f"  ✓ Converted instances.json → instances_consolidated.csv ({len(data)} rows)")
        else:
            # Create empty CSV with standard EC2 instance fields
            fieldnames = [
                'account_id', 'region', 'instance_id', 'instance_type', 'state',
                'availability_zone', 'launch_time', 'private_ip', 'public_ip',
                'vpc_id', 'subnet_id', 'ami_id', 'tenancy', 'hypervisor',
                'architecture', 'monitoring', 'cpu_cores', 'threads_per_core',
                'security_groups', 'ebs_volumes', 'network_interfaces', 'tags'
            ]
            with open(instances_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            print(f"  ✓ Created empty instances_consolidated.csv")
    
    # Convert volumes.json
    volumes_json = inventory_dir / "volumes.json"
    volumes_csv = inventory_dir / "volumes_consolidated.csv"
    
    if volumes_json.exists():
        with open(volumes_json, 'r') as f:
            data = json.load(f)
        
        if data and len(data) > 0:
            # Flatten nested structures
            flattened_data = []
            for vol in data:
                flat_vol = {}
                for key, value in vol.items():
                    if key == 'tags' and isinstance(value, dict):
                        flat_vol[key] = ';'.join(f"{k}={v}" for k, v in value.items())
                    elif key == 'attachments' and isinstance(value, list):
                        flat_vol[key] = ';'.join(str(a) for a in value)
                    else:
                        flat_vol[key] = value
                flattened_data.append(flat_vol)
            
            fieldnames = list(flattened_data[0].keys())
            with open(volumes_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(flattened_data)
            print(f"  ✓ Converted volumes.json → volumes_consolidated.csv ({len(flattened_data)} rows)")
        else:
            # Create empty CSV with standard EBS volume fields
            fieldnames = [
                'account_id', 'region', 'volume_id', 'size_gb', 'volume_type',
                'iops', 'throughput', 'encrypted', 'state', 'availability_zone',
                'snapshot_id', 'create_time', 'attachments', 'tags'
            ]
            with open(volumes_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            print(f"  ✓ Created empty volumes_consolidated.csv")
    
    # Convert regions.json
    regions_json = inventory_dir / "regions.json"
    regions_csv = inventory_dir / "regions_consolidated.csv"
    
    if regions_json.exists():
        with open(regions_json, 'r') as f:
            data = json.load(f)
        
        if data and len(data) > 0:
            fieldnames = list(data[0].keys())
            with open(regions_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            print(f"  ✓ Converted regions.json → regions_consolidated.csv ({len(data)} rows)")
        else:
            fieldnames = ['region_name', 'endpoint']
            with open(regions_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            print(f"  ✓ Created empty regions_consolidated.csv")
    
    # Delete JSON files
    for json_file in [instances_json, volumes_json, regions_json]:
        if json_file.exists():
            json_file.unlink()
            print(f"  ✓ Deleted {json_file.name}")


if __name__ == "__main__":
    print("Converting JSON inventory files to CSV...")
    convert_json_to_csv()
    print("\n✓ Conversion complete!")

