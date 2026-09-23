# Data Resources

The links below are retained from earlier project research. They are not
repository dependencies or a reproducible account of the committed demo
fixture's provenance. The current generator creates fixtures in Python; it does
not download these datasets or read the previously described CSV pipeline.

Current collection, seeding, and write behavior live in
[Data pipeline](DATA_PIPELINE.md). Live pricing collection uses boto3 in
[collectors/pricing.py](../aws_collector/collectors/pricing.py); it does not import
a downloaded AWS pricing CSV. Project research conclusions and future dataset
choices belong in [Notion project context](https://app.notion.com/p/28b0a821b3cc8061adebea034b7da111).

## Historical research links

| Reference | Recorded research topic |
| --- | --- |
| [Bitbrains GWA-T-12](https://www.kaggle.com/datasets/gauravdhamane/gwa-bitbrains), [original source](http://gwa.ewi.tudelft.nl/datasets/gwa-t-12-bitbrains) | VM utilization; Shen et al., CCGrid 2015 |
| [Numenta Anomaly Benchmark](https://github.com/numenta/NAB), [Kaggle mirror](https://www.kaggle.com/datasets/boltzmannbrain/nab) | Anomaly detection; Lavin and Ahmad, ICMLA 2015 |
| [EC2 instance metrics](https://www.kaggle.com/datasets/sakthivelank/ec2-instance-metricscpumemory-and-disk-usage) | CloudWatch-like metric samples |
| [Cloud resource usage](https://www.kaggle.com/datasets/programmer3/cloud-resource-usage-dataset-for-anomaly-detection) | Labeled anomaly samples |
| [Cloud workload job traces](https://www.kaggle.com/datasets/zoya77/cloud-workload-job-traces-for-resource-forecasting) | Forecasting research |
| [AWS pricing dataset](https://www.kaggle.com/datasets/justsahil/aws-pricing-dataset) | Historical pricing snapshots |
| [AWS EC2 pricing CSV](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/index.csv) | Alternative pricing reference |
| [Azure Public Dataset](https://github.com/Azure/AzurePublicDataset) | Alternative VM traces |
| [Google Cluster Trace](https://github.com/google/cluster-data) | Alternative job traces |
| [AWS Spot Price Archive](https://zenodo.org/records/5880793) | Historical Spot pricing |
| [Cloud dataset survey](https://dl.acm.org/doi/10.1145/3719003) | Literature review |

These links alone do not demonstrate that a dataset was used or validated.
Before claiming a new evaluation result, retain its input/version, parameters,
code revision, and reproducible output in the evidence source and link it.
