"""Anomaly detection for cost time series.

Run BEFORE forecasting to flag outliers that would corrupt training.
"""

import pandas as pd
import numpy as np


def detect_zscore(
    series: pd.Series,
    window: int = 30,
    threshold: float = 3.0,
) -> pd.Series:
    """Rolling Z-score anomaly detection.

    Args:
        series: Values to check (e.g., daily costs).
        window: Rolling window size for mean/std calculation.
        threshold: Z-score threshold (default 3 = 99.7% of normal data).

    Returns:
        Boolean Series where True = anomaly.
    """
    rolling_mean = series.rolling(window=window, min_periods=1).mean()
    rolling_std = series.rolling(window=window, min_periods=1).std()

    # Avoid division by zero
    rolling_std = rolling_std.replace(0, np.nan)

    z_scores = (series - rolling_mean) / rolling_std

    return z_scores.abs() > threshold


def detect_iqr(
    series: pd.Series,
    multiplier: float = 1.5,
) -> pd.Series:
    """IQR-based outlier detection.

    Args:
        series: Values to check.
        multiplier: IQR multiplier for bounds (1.5 = standard, 3.0 = extreme only).

    Returns:
        Boolean Series where True = anomaly.
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1

    lower_bound = q1 - multiplier * iqr
    upper_bound = q3 + multiplier * iqr

    return (series < lower_bound) | (series > upper_bound)


def flag_anomalies(
    df: pd.DataFrame,
    value_col: str,
    methods: list[str] | None = None,
    zscore_window: int = 30,
    zscore_threshold: float = 3.0,
    iqr_multiplier: float = 1.5,
) -> pd.DataFrame:
    """Add 'is_anomaly' column to DataFrame.

    Args:
        df: DataFrame with time series data.
        value_col: Column name containing values to check.
        methods: List of methods to use. Default: ['zscore', 'iqr'].
        zscore_window: Window size for Z-score method.
        zscore_threshold: Threshold for Z-score method.
        iqr_multiplier: Multiplier for IQR method.

    Returns:
        DataFrame with added 'is_anomaly' boolean column.
        Anomaly = True if flagged by ANY method (union).
    """
    if methods is None:
        methods = ["zscore", "iqr"]

    result = df.copy()
    series = result[value_col]

    anomaly_mask = pd.Series(False, index=result.index)

    if "zscore" in methods:
        zscore_anomalies = detect_zscore(series, zscore_window, zscore_threshold)
        anomaly_mask = anomaly_mask | zscore_anomalies

    if "iqr" in methods:
        iqr_anomalies = detect_iqr(series, iqr_multiplier)
        anomaly_mask = anomaly_mask | iqr_anomalies

    result["is_anomaly"] = anomaly_mask.fillna(False)

    return result
