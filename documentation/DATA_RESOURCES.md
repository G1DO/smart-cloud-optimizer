# Data Resources

External datasets used in this project. All downloaded and stored locally.

---

## 1. Primary Data

| Folder | Dataset | Download Link |
| --- | --- | --- |
| `bitbrains/` | Bitbrains GWA-T-12 (fastStorage + Rnd) | <https://www.kaggle.com/datasets/gauravdhamane/gwa-bitbrains> |

- **What**: Performance metrics from 1,750 VMs in a managed hosting datacenter. CPU, memory, disk I/O, network at 5-minute intervals.
- **Feeds**: `ec2_metrics.csv`, cost derivation for `daily_costs.csv`
- **Why**: Largest publicly available VM utilization dataset with real enterprise workload patterns. Peer-reviewed.
- **Original**: <http://gwa.ewi.tudelft.nl/datasets/gwa-t-12-bitbrains>
- **Citation**: Shen, S. et al. "Statistical Characterization of Business-Critical Workloads Hosted in Cloud Datacenters." *IEEE/ACM CCGrid*, 2015.

---

## 2. Supporting Data

| Folder | Dataset | Download Link |
| --- | --- | --- |
| `nab/` | Numenta Anomaly Benchmark | <https://www.kaggle.com/datasets/boltzmannbrain/nab> |
| `ec2_metrics/` | EC2 Instance Metrics (CPU, Memory, Disk) | <https://www.kaggle.com/datasets/sakthivelank/ec2-instance-metricscpumemory-and-disk-usage> |
| `anomaly/` | Cloud Resource Usage for Anomaly Detection | <https://www.kaggle.com/datasets/programmer3/cloud-resource-usage-dataset-for-anomaly-detection> |
| `workload_traces/` | Cloud Workload Job Traces for Forecasting | <https://www.kaggle.com/datasets/zoya77/cloud-workload-job-traces-for-resource-forecasting> |
| `pricing/` | AWS Pricing Dataset | <https://www.kaggle.com/datasets/justsahil/aws-pricing-dataset> |

### NAB — Numenta Anomaly Benchmark

- **What**: 50+ labeled time-series files including actual AWS CloudWatch metrics (CPU, network bytes, disk reads) with expert-labeled anomaly windows.
- **Feeds**: `ec2_metrics.csv`, anomaly detection validation
- **Why**: Only public dataset with labeled AWS anomalies. Ground truth for spike detection.
- **Source code**: <https://github.com/numenta/NAB>
- **Citation**: Lavin, A. & Ahmad, S. "Evaluating Real-time Anomaly Detection Algorithms — the Numenta Anomaly Benchmark." *IEEE ICMLA*, 2015.

### EC2 Instance Metrics (sakthivelank)

- **What**: Time-series system metrics from a real AWS EC2 instance over one full day. CPU, memory, disk utilization with simulated load spikes.
- **Feeds**: `ec2_metrics.csv` validation
- **Why**: Confirms the pipeline correctly handles native AWS CloudWatch metric format.
- **License**: MIT

### Cloud Resource Usage for Anomaly Detection (programmer3)

- **What**: 1,440 rows of timestamped cloud metrics (CPU, memory, disk I/O, network I/O) with anomaly labels. Includes workload types (Web Service, Backup, Crypto Mining).
- **Feeds**: `ec2_metrics.csv`, anomaly module validation
- **Why**: Second labeled anomaly source alongside NAB.
- **License**: CC0 Public Domain

### Cloud Workload Job Traces (zoya77)

- **What**: 3,562 job records from a distributed cloud environment with CPU/memory usage, queue times, and scheduling data.
- **Feeds**: Forecasting engine benchmark
- **Why**: Tests Prophet/SARIMAX generalization on a different workload distribution than Bitbrains.
- **License**: CC0 Public Domain

### AWS Pricing Dataset (justsahil)

- **What**: Pre-scraped snapshot of AWS pricing across all services. ~400 MB, updated weekly.
- **Feeds**: `instance_pricing.csv` cross-validation
- **Why**: Second source to verify pricing accuracy alongside the live AWS Pricing API.
- **License**: MIT

---

## 3. Additional Sources

Used by the system but not downloaded as Kaggle datasets.

### AWS EC2 Pricing API (Official)

- **What**: Live pricing data for all EC2 instance types. On-Demand, Reserved, and Spot prices.
- **Feeds**: `instance_pricing.csv`
- **URL**: <https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/index.csv>
- **Citation**: AWS Documentation

### AWS Account Data (Real Mode)

- **What**: Your own AWS account's Cost Explorer, CloudWatch, and inventory data collected via `aws_collector/`.
- **Feeds**: All `data/real/*.csv` files
- **Requires**: Configured AWS credentials with appropriate IAM permissions.

---

## 4. Literature Review References

Not used directly in the system. Cited to justify dataset choices.

| Source | Why Referenced |
| --- | --- |
| Azure Public Dataset V2 — <https://github.com/Azure/AzurePublicDataset> | 2M+ VMs. Justifies choosing Bitbrains (right granularity, manageable size). Cite: Cortez et al., *ACM SOSP*, 2017. |
| Google Cluster Trace 2019 — <https://github.com/google/cluster-data> | Shows consideration of alternatives (VM-level vs. job-level granularity). |
| AWS Spot Price Archive — <https://zenodo.org/records/5880793> | Historical Spot prices 2014–2021. Validates volatility assumptions. |
| ACM Computing Surveys 2025 — <https://dl.acm.org/doi/10.1145/3719003> | Comprehensive survey of public cloud datasets. Cite: Liu, G. et al., *ACM Computing Surveys*, 2025. |

---

## Summary

| # | Dataset | Role |
| --- | --- | --- |
| 1 | Bitbrains GWA-T-12 | Primary VM utilization data |
| 2 | NAB realAWSCloudwatch | Anomaly detection ground truth |
| 3 | sakthivelank EC2 Metrics | Pipeline format validation |
| 4 | programmer3 Cloud Usage | Second anomaly source |
| 5 | zoya77 Job Traces | Forecasting benchmark |
| 6 | justsahil AWS Pricing | Pricing cross-validation |
| 7 | AWS Pricing API (live) | Optimizer pricing input |
| 8 | AWS Account (real mode) | Real-world validation |
