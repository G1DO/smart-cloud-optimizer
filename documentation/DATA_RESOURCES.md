# Data Resources

External datasets and references used in this project, organized by role in the system.

All URLs verified as of February 2026.

---

## 1. Primary Sources

Directly used in the data pipeline. These feed into the system's CSV files.

### 1.1 Bitbrains GWA-T-12 Traces

- **What**: Performance metrics from 1,750 VMs in a managed hosting datacenter (banks, insurers). CPU, memory, disk I/O, network at 5-minute intervals.
- **Feeds**: `ec2_metrics.csv`, cost derivation for `daily_costs.csv`
- **Why**: Largest publicly available VM utilization dataset with real enterprise workload patterns. Peer-reviewed.
- **URL**: <https://kaggle.com/datasets/gauravdhamane/gwa-bitbrains>
- **Original**: <http://gwa.ewi.tudelft.nl/datasets/gwa-t-12-bitbrains>
- **Citation**: Shen, S. et al. "Statistical Characterization of Business-Critical Workloads Hosted in Cloud Datacenters." *IEEE/ACM CCGrid*, 2015.

### 1.2 Numenta Anomaly Benchmark (NAB) — realAWSCloudwatch Subset

- **What**: 50+ labeled time-series files including actual AWS CloudWatch metrics (CPU utilization, network bytes, disk reads) with expert-labeled anomaly windows.
- **Feeds**: `ec2_metrics.csv`, anomaly detection validation
- **Why**: Only public dataset with labeled AWS anomalies. Ground truth for spike detection.
- **URL**: <https://kaggle.com/datasets/boltzmannbrain/nab>
- **Source code**: <https://github.com/numenta/NAB>
- **Citation**: Lavin, A. & Ahmad, S. "Evaluating Real-time Anomaly Detection Algorithms — the Numenta Anomaly Benchmark." *IEEE ICMLA*, 2015.

### 1.3 AWS EC2 Pricing API (Official)

- **What**: Live pricing data for all EC2 instance types across all regions. On-Demand, Reserved, and Spot prices.
- **Feeds**: `instance_pricing.csv`
- **Why**: Authoritative source. The optimizer requires accurate pricing to produce credible recommendations.
- **URL**: <https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/index.csv>
- **Citation**: AWS Documentation — no paper needed, cite the API endpoint.

---

## 2. Supporting Sources

Used for validation and cross-checking. Strengthen evaluation by showing the system works across multiple data sources.

### 2.1 EC2 Instance Metrics — CPU, Memory, Disk (sakthivelank)

- **What**: Time-series system metrics from a real AWS EC2 instance over one full day. CPU, memory, disk utilization with simulated load spikes.
- **Feeds**: `ec2_metrics.csv` validation
- **Why**: Confirms the pipeline correctly handles native AWS CloudWatch metric format (not just converted Bitbrains data).
- **URL**: <https://kaggle.com/datasets/sakthivelank/ec2-instance-metricscpumemory-and-disk-usage>
- **License**: MIT

### 2.2 AWS Pricing Dataset (justsahil)

- **What**: Pre-scraped snapshot of AWS pricing across all services. ~400 MB, updated weekly.
- **Feeds**: `instance_pricing.csv` cross-validation
- **Why**: Faster than parsing the 1 GB+ official CSV. Provides a second source to verify pricing accuracy.
- **URL**: <https://kaggle.com/datasets/justsahil/aws-pricing-dataset>
- **License**: MIT

### 2.3 Cloud Resource Usage for Anomaly Detection (programmer3)

- **What**: 1,440 rows of timestamped cloud metrics (CPU, memory, disk I/O, network I/O) with anomaly labels. Includes workload types (Web Service, Backup, Crypto Mining).
- **Feeds**: `ec2_metrics.csv`, anomaly module validation
- **Why**: Second labeled anomaly source alongside NAB. Tests detection across different anomaly patterns.
- **URL**: <https://kaggle.com/datasets/programmer3/cloud-resource-usage-dataset-for-anomaly-detection>
- **License**: CC0 Public Domain

---

## 3. Supplementary Sources

Referenced in the literature review. Justify design decisions and show awareness of the field.

### 3.1 Cloud Workload Job Traces (zoya77)

- **What**: 3,562 job records from a distributed cloud environment with CPU/memory usage, queue times, and scheduling data.
- **Use**: Benchmarks Prophet/SARIMAX forecasting generalization on a different workload distribution than Bitbrains.
- **URL**: <https://kaggle.com/datasets/zoya77/cloud-workload-job-traces-for-resource-forecasting>
- **License**: CC0 Public Domain

### 3.2 Azure Public Dataset V2

- **What**: VM traces from 2M+ VMs across Azure datacenters (2017, 2019). Also includes Azure Functions traces and LLM inference traces.
- **Use**: Literature review. Demonstrates awareness of industry-scale traces. Justifies choosing Bitbrains (right granularity, manageable size).
- **URL**: <https://github.com/Azure/AzurePublicDataset>
- **Citation**: Cortez, E. et al. "Resource Central: Understanding and Predicting Workloads for Improved Resource Management in Large Cloud Platforms." *ACM SOSP*, 2017.

### 3.3 Google Cluster Trace 2019

- **What**: Workload traces from Google Borg cluster management system. Three versions (2009, 2011, 2019), plus power consumption data.
- **Use**: Literature review. Shows consideration of alternatives and why Bitbrains was chosen over Google traces (VM-level vs. job-level granularity).
- **URL**: <https://github.com/google/cluster-data>
- **License**: CC-BY

### 3.4 AWS Spot Price Historical Archive

- **What**: Amazon EC2 Spot price history covering 2014–2015 and 2017–2021. ~5.4 GB across all regions.
- **Use**: Validates Spot price volatility assumptions in the optimizer.
- **URL**: <https://zenodo.org/records/5880793>
- **Author**: Calvin Ardi
- **License**: CC0

---

## 4. Survey Reference

### 4.1 Public Datasets for Cloud Computing: A Comprehensive Survey

- **What**: Systematic survey of publicly available cloud computing datasets — load traces, network traces, and benchmarks.
- **Use**: Proves a proper dataset survey was conducted. Covers energy efficiency prediction, workload analysis, and anomaly detection.
- **URL**: <https://dl.acm.org/doi/10.1145/3719003>
- **Citation**: Liu, G., Lin, W. et al. "Public Datasets for Cloud Computing: A Comprehensive Survey." *ACM Computing Surveys*, 2025.

---

## Summary Table

| # | Source | Type | Role in Project |
| --- | --- | --- | --- |
| 1 | Bitbrains GWA-T-12 | VM metrics | Primary utilization data |
| 2 | NAB realAWSCloudwatch | Labeled anomalies | Anomaly detection ground truth |
| 3 | AWS Pricing API | Live pricing | Optimizer pricing input |
| 4 | sakthivelank EC2 Metrics | EC2 metrics | Pipeline format validation |
| 5 | justsahil AWS Pricing | Pricing snapshot | Pricing cross-validation |
| 6 | programmer3 Cloud Usage | Labeled anomalies | Second anomaly source |
| 7 | zoya77 Job Traces | Job traces | Forecasting benchmark |
| 8 | Azure Public Dataset V2 | VM traces | Literature review |
| 9 | Google Cluster Trace | Cluster traces | Literature review |
| 10 | Zenodo Spot Archive | Spot prices | Spot volatility validation |
| 11 | ACM Survey 2025 | Survey paper | Methodology justification |
