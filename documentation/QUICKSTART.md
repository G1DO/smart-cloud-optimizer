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

The database ships with pre-loaded synthetic data -- no generation step needed.

```bash
streamlit run app.py
```

On the login screen, click **"Try Demo Mode"**. This logs in with a pre-seeded demo account and gives you access to:

- 365 days of cost data (~$50-$150/day)
- 8 EC2 instances with realistic CPU profiles
- 2 RDS instances, 3 ElastiCache nodes, 4 ECS services
- 4 Lambda functions, 3 DynamoDB tables, 4 S3 buckets
- Pricing data for all services
- Pre-generated optimization recommendations

---

## Verify It Works

Run the test suite:

```bash
python -m pytest tests/ -v
```

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

## Run the Dashboard

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. You will see a login screen with three options:

1. **Login** -- Sign in with an existing account
2. **Register** -- Create a new account
3. **Try Demo Mode** -- Explore with pre-loaded synthetic data (no account required)

After authentication, the dashboard shows 5 pages: Home, Costs, Forecasts, Recommendations, Settings.

## CLI Tools

```bash
# Run optimizer (generates cost-saving recommendations)
python -m optimizer --user-id aws-SYNTHETIC-001

# Run ML forecasting
python -m ml_engine --user-id aws-SYNTHETIC-001
```

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
