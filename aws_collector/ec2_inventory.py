"""
EC2 Inventory Collection Module
Collects EC2 instance information and metrics
"""
import csv
from datetime import datetime
from pathlib import Path
from typing import List

from .config import Config


class EC2Inventory:
    """EC2 inventory and metrics collector"""
    
    def __init__(self, session, account_id: str, regions: List[str]):
        self.session = session
        self.account_id = account_id
        self.regions = regions
    
    def export_instances(self):
        """Export detailed EC2 inventory to CSV"""
        rows = []
        
        for region in self.regions:
            print(f"[EC2] Scanning region {region} ...")
            ec2 = self.session.client("ec2", region_name=region)
            
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
                            "account_id": self.account_id,
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
        
        csv_path = Config.get_csv_path(Config.EC2_INSTANCES_CSV)
        print(f"[EC2] Writing {len(rows)} instances to {csv_path} ...")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        return csv_path

