"""
ML Utilities for Data Preparation
Helper functions to prepare collected data for ML model training
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from .config import DATA_DIR


def load_cost_data(month_key: str = None) -> pd.DataFrame:
    """
    Load cost data from CSV files
    
    Args:
        month_key: Specific month (YYYY-MM) or None for all months
    
    Returns:
        DataFrame with cost data
    """
    cost_dir = DATA_DIR / "cost"
    
    if month_key:
        months = [month_key]
    else:
        months = [d.name for d in cost_dir.iterdir() if d.is_dir()]
    
    dfs = []
    for month in months:
        month_dir = cost_dir / month
        daily_file = month_dir / "daily_cost.csv"
        if daily_file.exists():
            df = pd.read_csv(daily_file)
            df['month'] = month
            dfs.append(df)
    
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()


def load_ec2_metrics(month_key: str = None, instance_id: str = None) -> pd.DataFrame:
    """
    Load EC2 metrics from CSV files
    
    Args:
        month_key: Specific month (YYYY-MM) or None for all months
        instance_id: Specific instance ID or None for all instances
    
    Returns:
        DataFrame with EC2 metrics
    """
    metrics_dir = DATA_DIR / "metrics" / "ec2"
    
    # Check for consolidated file directly (new structure)
    consolidated_file = metrics_dir / "ec2_metrics_consolidated.csv"
    if consolidated_file.exists():
        df = pd.read_csv(consolidated_file)
        if instance_id:
            df = df[df.get('instance_id', '') == instance_id]
        return df
    
    # Fallback to old monthly structure if exists
    if month_key:
        months = [month_key]
    else:
        months = [d.name for d in metrics_dir.iterdir() if d.is_dir() and d.name != '__pycache__']
    
    dfs = []
    for month in months:
        month_dir = metrics_dir / month
        if not month_dir.exists():
            continue
        for csv_file in month_dir.glob("*.csv"):
            if instance_id and instance_id not in csv_file.stem:
                continue
            
            df = pd.read_csv(csv_file)
            df['month'] = month
            dfs.append(df)
    
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        # Convert timestamp to datetime
        if 'timestamp' in combined.columns:
            combined['timestamp'] = pd.to_datetime(combined['timestamp'])
        return combined
    return pd.DataFrame()


def load_rds_metrics(month_key: str = None, db_id: str = None) -> pd.DataFrame:
    """
    Load RDS metrics from CSV files
    
    Args:
        month_key: Specific month (YYYY-MM) or None for all months
        db_id: Specific DB instance ID or None for all instances
    
    Returns:
        DataFrame with RDS metrics
    """
    metrics_dir = DATA_DIR / "metrics" / "rds"
    
    # Check for consolidated file directly (new structure)
    consolidated_file = metrics_dir / "rds_metrics_consolidated.csv"
    if consolidated_file.exists():
        df = pd.read_csv(consolidated_file)
        if db_id:
            df = df[df.get('db_instance_id', '') == db_id]
        return df
    
    # Fallback to old monthly structure if exists
    if month_key:
        months = [month_key]
    else:
        months = [d.name for d in metrics_dir.iterdir() if d.is_dir() and d.name != '__pycache__']
    
    dfs = []
    for month in months:
        month_dir = metrics_dir / month
        if not month_dir.exists():
            continue
        for csv_file in month_dir.glob("*.csv"):
            if db_id and db_id not in csv_file.stem:
                continue
            
            df = pd.read_csv(csv_file)
            df['month'] = month
            dfs.append(df)
    
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        if 'timestamp' in combined.columns:
            combined['timestamp'] = pd.to_datetime(combined['timestamp'])
        return combined
    return pd.DataFrame()


def add_time_features(df: pd.DataFrame, timestamp_col: str = 'timestamp') -> pd.DataFrame:
    """
    Add time-based features for ML models
    
    Args:
        df: DataFrame with timestamp column
        timestamp_col: Name of timestamp column
    
    Returns:
        DataFrame with added time features
    """
    if timestamp_col not in df.columns:
        return df
    
    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    
    # Extract time features
    df['hour'] = df[timestamp_col].dt.hour
    df['day_of_week'] = df[timestamp_col].dt.dayofweek  # 0=Monday, 6=Sunday
    df['day_of_month'] = df[timestamp_col].dt.day
    df['week_of_year'] = df[timestamp_col].dt.isocalendar().week
    df['month'] = df[timestamp_col].dt.month
    df['year'] = df[timestamp_col].dt.year
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    
    # Cyclical encoding for periodic features
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    
    return df


def prepare_for_training(df: pd.DataFrame, target_col: str, 
                        exclude_cols: List[str] = None) -> tuple:
    """
    Prepare data for ML training
    
    Args:
        df: Input DataFrame
        target_col: Name of target column
        exclude_cols: Columns to exclude from features
    
    Returns:
        Tuple of (X_features, y_target)
    """
    import numpy as np
    
    exclude_cols = exclude_cols or []
    exclude_cols.extend(['timestamp', 'account_id', target_col])
    
    # Select feature columns
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    # Convert to numeric where possible
    X = df[feature_cols].copy()
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors='coerce')
    
    # Fill missing values
    X = X.fillna(X.mean())
    
    # Target variable
    y = pd.to_numeric(df[target_col], errors='coerce')
    
    return X, y


def aggregate_metrics(df: pd.DataFrame, group_by: List[str], 
                      agg_funcs: Dict[str, List[str]] = None) -> pd.DataFrame:
    """
    Aggregate metrics for time series analysis
    
    Args:
        df: Input DataFrame
        group_by: Columns to group by
        agg_funcs: Dictionary of column -> aggregation functions
    
    Returns:
        Aggregated DataFrame
    """
    if agg_funcs is None:
        # Default aggregations for common metric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        agg_funcs = {col: ['mean', 'max', 'min', 'std'] for col in numeric_cols}
    
    return df.groupby(group_by).agg(agg_funcs).reset_index()


def create_lag_features(df: pd.DataFrame, columns: List[str], 
                       lags: List[int] = [1, 7, 30]) -> pd.DataFrame:
    """
    Create lag features for time series forecasting
    
    Args:
        df: Input DataFrame (must be sorted by timestamp)
        columns: Columns to create lags for
        lags: List of lag periods
    
    Returns:
        DataFrame with lag features
    """
    df = df.sort_values('timestamp').copy()
    
    for col in columns:
        for lag in lags:
            df[f'{col}_lag_{lag}'] = df[col].shift(lag)
    
    return df

