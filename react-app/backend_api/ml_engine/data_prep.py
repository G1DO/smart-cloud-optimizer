"""
data_prep.py — ML data preparation utilities.

Helper functions to prepare collected data for ML model training,
including time-feature engineering, lag creation, and aggregation.
All data loading reads from SQLite via the storage API.

Part of the Smart Cloud Optimizer graduation project.
"""
import sqlite3
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

import storage


def load_cost_data(conn: sqlite3.Connection, user_id: str,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> pd.DataFrame:
    """Load daily cost data from the database.

    Args:
        conn: Open database connection.
        user_id: User ID to query.
        start_date: Inclusive start date (YYYY-MM-DD).
        end_date: Inclusive end date (YYYY-MM-DD).

    Returns:
        DataFrame with columns: date, total_cost.
    """
    rows = storage.get_daily_costs(conn, user_id,
                                   start_date=start_date,
                                   end_date=end_date)
    if not rows:
        return pd.DataFrame(columns=["date", "total_cost"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_ec2_metrics(conn: sqlite3.Connection, user_id: str,
                     instance_id: Optional[str] = None,
                     start: Optional[str] = None,
                     end: Optional[str] = None) -> pd.DataFrame:
    """Load EC2 metrics from the database.

    Args:
        conn: Open database connection.
        user_id: User ID to query.
        instance_id: Optional filter by instance.
        start: Inclusive start timestamp.
        end: Inclusive end timestamp.

    Returns:
        DataFrame with EC2 metrics.
    """
    rows = storage.get_ec2_metrics(conn, user_id,
                                   instance_id=instance_id,
                                   start=start, end=end)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def load_rds_metrics(conn: sqlite3.Connection, user_id: str,
                     db_instance_id: Optional[str] = None,
                     start: Optional[str] = None,
                     end: Optional[str] = None) -> pd.DataFrame:
    """Load RDS metrics from the database.

    Args:
        conn: Open database connection.
        user_id: User ID to query.
        db_instance_id: Optional filter by DB instance.
        start: Inclusive start timestamp.
        end: Inclusive end timestamp.

    Returns:
        DataFrame with RDS metrics.
    """
    rows = storage.get_rds_metrics(conn, user_id,
                                   db_instance_id=db_instance_id,
                                   start=start, end=end)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def _load_metrics(conn: sqlite3.Connection, getter, user_id: str,
                  time_col: str = "timestamp", **kwargs) -> pd.DataFrame:
    """Internal helper — call a storage.get_*_metrics function and return a DataFrame."""
    rows = getter(conn, user_id, **kwargs)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if time_col in df.columns:
        df[time_col] = pd.to_datetime(df[time_col])
    return df


def load_elasticache_metrics(conn: sqlite3.Connection, user_id: str,
                             cache_cluster_id: Optional[str] = None) -> pd.DataFrame:
    """Load ElastiCache metrics for a user."""
    return _load_metrics(conn, storage.get_elasticache_metrics, user_id,
                         cache_cluster_id=cache_cluster_id)


def load_ecs_metrics(conn: sqlite3.Connection, user_id: str,
                     service_name: Optional[str] = None) -> pd.DataFrame:
    """Load ECS metrics for a user."""
    return _load_metrics(conn, storage.get_ecs_metrics, user_id,
                         service_name=service_name)


def load_lambda_metrics(conn: sqlite3.Connection, user_id: str,
                        function_name: Optional[str] = None) -> pd.DataFrame:
    """Load Lambda metrics for a user."""
    return _load_metrics(conn, storage.get_lambda_metrics, user_id,
                         time_col="date", function_name=function_name)


def load_dynamodb_metrics(conn: sqlite3.Connection, user_id: str,
                          table_name: Optional[str] = None) -> pd.DataFrame:
    """Load DynamoDB metrics for a user."""
    return _load_metrics(conn, storage.get_dynamodb_metrics, user_id,
                         table_name=table_name)


def load_ebs_metrics(conn: sqlite3.Connection, user_id: str,
                     volume_id: Optional[str] = None) -> pd.DataFrame:
    """Load EBS metrics for a user."""
    return _load_metrics(conn, storage.get_ebs_metrics, user_id,
                         volume_id=volume_id)


def load_s3_metrics(conn: sqlite3.Connection, user_id: str,
                    bucket_name: Optional[str] = None) -> pd.DataFrame:
    """Load S3 metrics for a user."""
    return _load_metrics(conn, storage.get_s3_metrics, user_id,
                         bucket_name=bucket_name)


def load_nat_gateway_metrics(conn: sqlite3.Connection, user_id: str,
                             nat_gateway_id: Optional[str] = None) -> pd.DataFrame:
    """Load NAT Gateway metrics for a user."""
    return _load_metrics(conn, storage.get_nat_gateway_metrics, user_id,
                         nat_gateway_id=nat_gateway_id)


def load_elb_metrics(conn: sqlite3.Connection, user_id: str,
                     elb_arn: Optional[str] = None) -> pd.DataFrame:
    """Load ELB metrics for a user."""
    return _load_metrics(conn, storage.get_elb_metrics, user_id,
                         elb_arn=elb_arn)


# Dispatcher: load metrics for any service by name
_SERVICE_LOADERS = {
    "ec2": load_ec2_metrics,
    "rds": load_rds_metrics,
    "elasticache": load_elasticache_metrics,
    "ecs": load_ecs_metrics,
    "lambda": load_lambda_metrics,
    "dynamodb": load_dynamodb_metrics,
    "ebs": load_ebs_metrics,
    "s3": load_s3_metrics,
    "nat_gateway": load_nat_gateway_metrics,
    "elb": load_elb_metrics,
}


def load_service_metrics(conn: sqlite3.Connection, user_id: str,
                         service: str) -> pd.DataFrame:
    """Load metrics for any supported service by name.

    Args:
        conn: Open database connection.
        user_id: User ID to query.
        service: Service key (ec2, rds, elasticache, ecs, lambda,
                 dynamodb, ebs, s3, nat_gateway, elb).

    Returns:
        DataFrame with service metrics, or empty DataFrame if unknown service.
    """
    loader = _SERVICE_LOADERS.get(service.lower())
    if loader is None:
        return pd.DataFrame()
    return loader(conn, user_id)


def add_time_features(df: pd.DataFrame,
                      timestamp_col: str = "timestamp") -> pd.DataFrame:
    """Add time-based features for ML models.

    Args:
        df: DataFrame with timestamp column.
        timestamp_col: Name of timestamp column.

    Returns:
        DataFrame with added time features.
    """
    if timestamp_col not in df.columns:
        return df

    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    df["hour"] = df[timestamp_col].dt.hour
    df["day_of_week"] = df[timestamp_col].dt.dayofweek
    df["day_of_month"] = df[timestamp_col].dt.day
    df["week_of_year"] = df[timestamp_col].dt.isocalendar().week
    df["month"] = df[timestamp_col].dt.month
    df["year"] = df[timestamp_col].dt.year
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # Cyclical encoding for periodic features
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["day_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["day_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    return df


def prepare_for_training(df: pd.DataFrame, target_col: str,
                         exclude_cols: Optional[List[str]] = None) -> tuple:
    """Prepare data for ML training.

    Args:
        df: Input DataFrame.
        target_col: Name of target column.
        exclude_cols: Columns to exclude from features.

    Returns:
        Tuple of (X_features, y_target).
    """
    exclude_cols = list(exclude_cols or [])
    exclude_cols.extend(["timestamp", "user_id", target_col])

    feature_cols = [col for col in df.columns if col not in exclude_cols]

    X = df[feature_cols].copy()
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")

    X = X.fillna(X.mean())
    y = pd.to_numeric(df[target_col], errors="coerce")

    return X, y


def aggregate_metrics(df: pd.DataFrame, group_by: List[str],
                      agg_funcs: Optional[Dict[str, List[str]]] = None) -> pd.DataFrame:
    """Aggregate metrics for time series analysis.

    Args:
        df: Input DataFrame.
        group_by: Columns to group by.
        agg_funcs: Dictionary of column -> aggregation functions.

    Returns:
        Aggregated DataFrame.
    """
    if agg_funcs is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        agg_funcs = {col: ["mean", "max", "min", "std"] for col in numeric_cols}

    return df.groupby(group_by).agg(agg_funcs).reset_index()


def create_lag_features(df: pd.DataFrame, columns: List[str],
                        lags: Optional[List[int]] = None) -> pd.DataFrame:
    """Create lag features for time series forecasting.

    Args:
        df: Input DataFrame (must be sorted by timestamp).
        columns: Columns to create lags for.
        lags: List of lag periods. Defaults to [1, 7, 30].

    Returns:
        DataFrame with lag features.
    """
    if lags is None:
        lags = [1, 7, 30]
    df = df.sort_values("timestamp").copy()

    for col in columns:
        for lag in lags:
            df[f"{col}_lag_{lag}"] = df[col].shift(lag)

    return df
