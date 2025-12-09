# ML-Ready Data Format

All CSV files are structured for easy ML model training. Here's how to use them:

## Data Structure

### Cost Data (`data/cost/YYYY-MM/`)
- **daily_cost.csv**: Daily total costs
  - Columns: `account_id`, `date`, `cost_amount`, `currency`
  - Ready for time series forecasting

- **service_cost.csv**: Cost breakdown by service
  - Columns: `account_id`, `date`, `service_name`, `cost_amount`, `currency`
  - Good for service-level analysis

- **usage_type_cost.csv**: Cost by usage type
  - Columns: `account_id`, `date`, `usage_type`, `cost_amount`, `currency`

### Metrics Data (`data/metrics/{service}/YYYY-MM/`)
Each resource has its own CSV file with:
- **Timestamp**: ISO format datetime
- **Numeric metrics**: All values are floats (empty strings for missing)
- **Resource ID**: Instance ID, volume ID, function name, etc.

Example EC2 metrics columns:
- `timestamp`, `account_id`, `region`, `instance_id`
- `CPUUtilization_average`, `CPUUtilization_maximum`
- `NetworkIn_average`, `NetworkOut_average`
- `DiskReadOps_average`, `DiskWriteOps_average`

## Quick Start for ML

```python
from aws_collector.ml_utils import (
    load_cost_data,
    load_ec2_metrics,
    add_time_features,
    prepare_for_training
)
import pandas as pd

# Load cost data
cost_df = load_cost_data()  # All months
cost_df = load_cost_data('2024-10')  # Specific month

# Load EC2 metrics
ec2_df = load_ec2_metrics()  # All instances, all months
ec2_df = load_ec2_metrics(instance_id='i-1234567890abcdef0')

# Add time features for ML
ec2_df = add_time_features(ec2_df, timestamp_col='timestamp')
# Now you have: hour, day_of_week, month, is_weekend, hour_sin, hour_cos, etc.

# Prepare for training
X, y = prepare_for_training(
    ec2_df, 
    target_col='CPUUtilization_average',
    exclude_cols=['instance_id', 'region']
)

# Now X and y are ready for sklearn, xgboost, etc.
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
```

## Example: Cost Forecasting

```python
from aws_collector.ml_utils import load_cost_data, add_time_features, create_lag_features

# Load and prepare cost data
df = load_cost_data()
df = add_time_features(df, timestamp_col='date')
df = create_lag_features(df, columns=['cost_amount'], lags=[1, 7, 30])

# Train forecasting model
X, y = prepare_for_training(df, target_col='cost_amount')
```

## Example: Anomaly Detection

```python
from aws_collector.ml_utils import load_ec2_metrics, add_time_features
from sklearn.ensemble import IsolationForest

# Load metrics
df = load_ec2_metrics()
df = add_time_features(df)

# Prepare features
X, _ = prepare_for_training(df, target_col='CPUUtilization_average')

# Train anomaly detector
model = IsolationForest(contamination=0.1)
model.fit(X)
```

## Data Quality

- **Numeric values**: All metrics are floats (empty strings converted to NaN)
- **Timestamps**: Consistent ISO format, easy to parse
- **Missing values**: Handled gracefully (empty strings or NaN)
- **Consistent columns**: Same structure across all months

## Feature Engineering Helpers

The `ml_utils.py` module provides:
- `add_time_features()`: Adds hour, day, month, cyclical encodings
- `create_lag_features()`: Creates lagged features for time series
- `aggregate_metrics()`: Aggregates metrics by time periods
- `prepare_for_training()`: Cleans and prepares data for ML

## Tips

1. **Time Series**: Use `add_time_features()` and `create_lag_features()`
2. **Forecasting**: Target `cost_amount` or metric averages
3. **Anomaly Detection**: Use all metrics as features
4. **Clustering**: Group by service/region for pattern discovery
5. **Regression**: Predict costs or resource usage

All data is ready for pandas, sklearn, xgboost, prophet, and other ML libraries!

