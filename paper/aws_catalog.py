"""Verified AWS EC2 price/spec catalog for the external-validation experiment.

Region us-east-1, Linux, shared tenancy.
  od_hourly   = On-Demand $/hr
  ri1y_hourly = 1-yr Standard Reserved, No Upfront, $/hr

Source: AWS Price List Bulk API region file
https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv
(publication 2026-06-30T19:24:11Z, version 20260630192411), filtered to
Location="US East (N. Virginia)", Tenancy=Shared, OS=Linux,
Pre-Installed S/W=NA, CapacityStatus=Used, License=No License required.
Cross-checked 28/28 on-demand and 28/28 reserved rates against ec2.shop and
spot-checked against instances.vantage.sh (0 disagreements). vCPU/memory come
from the same AWS file's product columns.
"""

SNAPSHOT_DATE = "2026-06-30"

CATALOG = {
    "t3.micro":    {"vcpus": 2,  "memory_gb": 1.0,   "od_hourly": 0.0104, "ri1y_hourly": 0.0065},
    "t3.small":    {"vcpus": 2,  "memory_gb": 2.0,   "od_hourly": 0.0208, "ri1y_hourly": 0.0130},
    "t3.medium":   {"vcpus": 2,  "memory_gb": 4.0,   "od_hourly": 0.0416, "ri1y_hourly": 0.0261},
    "t3.large":    {"vcpus": 2,  "memory_gb": 8.0,   "od_hourly": 0.0832, "ri1y_hourly": 0.0522},
    "t3.xlarge":   {"vcpus": 4,  "memory_gb": 16.0,  "od_hourly": 0.1664, "ri1y_hourly": 0.1043},
    "t3.2xlarge":  {"vcpus": 8,  "memory_gb": 32.0,  "od_hourly": 0.3328, "ri1y_hourly": 0.2086},
    "m5.large":    {"vcpus": 2,  "memory_gb": 8.0,   "od_hourly": 0.0960, "ri1y_hourly": 0.0600},
    "m5.xlarge":   {"vcpus": 4,  "memory_gb": 16.0,  "od_hourly": 0.1920, "ri1y_hourly": 0.1210},
    "m5.2xlarge":  {"vcpus": 8,  "memory_gb": 32.0,  "od_hourly": 0.3840, "ri1y_hourly": 0.2420},
    "m5.4xlarge":  {"vcpus": 16, "memory_gb": 64.0,  "od_hourly": 0.7680, "ri1y_hourly": 0.4840},
    "m5.8xlarge":  {"vcpus": 32, "memory_gb": 128.0, "od_hourly": 1.5360, "ri1y_hourly": 0.9680},
    "m5.12xlarge": {"vcpus": 48, "memory_gb": 192.0, "od_hourly": 2.3040, "ri1y_hourly": 1.4520},
    "m5.16xlarge": {"vcpus": 64, "memory_gb": 256.0, "od_hourly": 3.0720, "ri1y_hourly": 1.9350},
    "m5.24xlarge": {"vcpus": 96, "memory_gb": 384.0, "od_hourly": 4.6080, "ri1y_hourly": 2.9030},
    "c5.large":    {"vcpus": 2,  "memory_gb": 4.0,   "od_hourly": 0.0850, "ri1y_hourly": 0.0540},
    "c5.xlarge":   {"vcpus": 4,  "memory_gb": 8.0,   "od_hourly": 0.1700, "ri1y_hourly": 0.1070},
    "c5.2xlarge":  {"vcpus": 8,  "memory_gb": 16.0,  "od_hourly": 0.3400, "ri1y_hourly": 0.2140},
    "c5.4xlarge":  {"vcpus": 16, "memory_gb": 32.0,  "od_hourly": 0.6800, "ri1y_hourly": 0.4280},
    "c5.9xlarge":  {"vcpus": 36, "memory_gb": 72.0,  "od_hourly": 1.5300, "ri1y_hourly": 0.9640},
    "c5.18xlarge": {"vcpus": 72, "memory_gb": 144.0, "od_hourly": 3.0600, "ri1y_hourly": 1.9280},
    "r5.large":    {"vcpus": 2,  "memory_gb": 16.0,  "od_hourly": 0.1260, "ri1y_hourly": 0.0790},
    "r5.xlarge":   {"vcpus": 4,  "memory_gb": 32.0,  "od_hourly": 0.2520, "ri1y_hourly": 0.1590},
    "r5.2xlarge":  {"vcpus": 8,  "memory_gb": 64.0,  "od_hourly": 0.5040, "ri1y_hourly": 0.3180},
    "r5.4xlarge":  {"vcpus": 16, "memory_gb": 128.0, "od_hourly": 1.0080, "ri1y_hourly": 0.6350},
    "r5.8xlarge":  {"vcpus": 32, "memory_gb": 256.0, "od_hourly": 2.0160, "ri1y_hourly": 1.2700},
    "r5.12xlarge": {"vcpus": 48, "memory_gb": 384.0, "od_hourly": 3.0240, "ri1y_hourly": 1.9050},
    "r5.16xlarge": {"vcpus": 64, "memory_gb": 512.0, "od_hourly": 4.0320, "ri1y_hourly": 2.5400},
    "r5.24xlarge": {"vcpus": 96, "memory_gb": 768.0, "od_hourly": 6.0480, "ri1y_hourly": 3.8100},
}
