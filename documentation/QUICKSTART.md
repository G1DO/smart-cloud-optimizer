# Quickstart

Get the project running in 5 minutes.

---

## Prerequisites

- Python 3.12+
- pip
- (Optional) AWS credentials for real data collection

---

## Setup

```bash
# Clone and enter the project
git clone <repo-url>
cd cloud-gp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Demo Mode (Recommended Start)

Load sample data to explore the system without AWS credentials:

```bash
python -m data_generation.synthetic --days 365 --seed 42
```

This creates a SQLite database at `data/cloud_optimizer.db` with:

- 365 days of cost data (~$50-$150/day)
- 8 EC2 instances with realistic CPU profiles
- 2 RDS instances, 3 ElastiCache nodes, 4 ECS services
- 4 Lambda functions, 3 DynamoDB tables, 4 S3 buckets
- Pricing data for all services

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--days` | `365` | Number of days to simulate |
| `--seed` | `42` | Random seed for reproducibility |

---

## Verify It Works

Run the test suite:

```bash
python -m pytest tests/ -v
```

Expected: 117 tests pass.

---

## Real AWS Data Collection

Requires configured AWS credentials with these IAM permissions:

- `ce:GetCostAndUsage`, `ce:GetAnomalies`
- `cloudwatch:GetMetricStatistics`
- `ec2:Describe*`, `rds:Describe*`, `lambda:ListFunctions`
- `s3:ListBuckets`, `elasticache:Describe*`, `ecs:Describe*`
- `elasticloadbalancing:Describe*`, `dynamodb:Describe*`
- `pricing:GetProducts`, `sts:GetCallerIdentity`

```bash
export DEMO_MODE=false
python -m aws_collector.main
```

This collects 12 months of data across all enabled AWS regions.

---

## Run the Dashboard (Stub)

```bash
streamlit run app.py
```

Note: Dashboard is partially implemented.

---

## Common Issues

### "No module named 'storage'"

Make sure you're in the project root and have activated the virtual environment:

```bash
cd cloud-gp
source venv/bin/activate
```

### "Database is locked"

Another process is using `data/cloud_optimizer.db`. Close other terminals or wait.

### Tests fail with import errors

Reinstall dependencies:

```bash
pip install -r requirements.txt
```

### AWS collection fails

Check your credentials: `aws sts get-caller-identity`

---

## Next Steps

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system
2. Read [MODULES.md](MODULES.md) to find specific code
3. Explore the database with [DATA_SCHEMAS.md](DATA_SCHEMAS.md)
