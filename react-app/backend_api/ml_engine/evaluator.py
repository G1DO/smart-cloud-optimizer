"""Model evaluation via time-series cross-validation.

Key functions:
- calc_metrics: MAPE, RMSE, MAE for a single prediction
- time_series_cv: Walk-forward CV returning metrics per fold
- compare_models: Run CV on multiple models, return comparison table
"""

import numpy as np
import pandas as pd


def calc_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculate forecast accuracy metrics.

    Args:
        y_true: Actual values.
        y_pred: Predicted values.

    Returns:
        Dict with mape, rmse, mae.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    # MAPE: Mean Absolute Percentage Error
    # Avoid division by zero
    mask = y_true != 0
    if mask.sum() > 0:
        mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
    else:
        mape = np.nan

    # RMSE: Root Mean Squared Error
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

    # MAE: Mean Absolute Error
    mae = np.mean(np.abs(y_true - y_pred))

    return {"mape": mape, "rmse": rmse, "mae": mae}


def time_series_cv(
    model,
    df: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "total_cost",
    initial: int = 60,
    horizon: int = 14,
    step: int = 7,
) -> list[dict]:
    """Walk-forward cross-validation for time series.

    Splits data into expanding training windows, forecasts `horizon` days,
    compares to actuals.

    Args:
        model: Forecaster instance (must have fit/predict methods).
        df: DataFrame with date and value columns.
        date_col: Date column name.
        value_col: Value column name.
        initial: Minimum training size (days).
        horizon: Forecast horizon (days).
        step: Days between CV folds.

    Returns:
        List of dicts, one per fold: {fold, train_size, mape, rmse, mae}.
    """
    # Prepare and sort data
    data = df[[date_col, value_col]].copy()
    data.columns = ["date", "value"]
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date").reset_index(drop=True)

    n = len(data)
    results = []
    fold = 0

    # Walk forward through the data
    cutoff = initial
    while cutoff + horizon <= n:
        train = data.iloc[:cutoff].copy()
        test = data.iloc[cutoff : cutoff + horizon].copy()

        # Fit fresh model instance
        model_copy = model.__class__(**_get_init_params(model))
        model_copy.fit(train, date_col="date", value_col="value")

        # Predict
        pred = model_copy.predict(horizon=len(test))

        # Calculate metrics
        metrics = calc_metrics(test["value"].values, pred["forecast"].values)
        metrics["fold"] = fold
        metrics["train_size"] = len(train)
        results.append(metrics)

        cutoff += step
        fold += 1

    return results


def _get_init_params(model) -> dict:
    """Extract __init__ parameters from a model instance.

    This is a simple approach - in production you'd use inspect or
    store params explicitly.
    """
    # Get parameters that were set in __init__
    params = {}

    # Check common parameters by model type
    if hasattr(model, "season_length"):
        params["season_length"] = model.season_length
    if hasattr(model, "seasonal_periods"):
        params["seasonal_periods"] = model.seasonal_periods
    if hasattr(model, "trend"):
        params["trend"] = model.trend
    if hasattr(model, "seasonal"):
        params["seasonal"] = model.seasonal
    if hasattr(model, "yearly_seasonality"):
        params["yearly_seasonality"] = model.yearly_seasonality
    if hasattr(model, "weekly_seasonality"):
        params["weekly_seasonality"] = model.weekly_seasonality
    if hasattr(model, "daily_seasonality"):
        params["daily_seasonality"] = model.daily_seasonality
    if hasattr(model, "seasonal_period"):
        params["seasonal_period"] = model.seasonal_period
    if hasattr(model, "max_p"):
        params["max_p"] = model.max_p
    if hasattr(model, "max_q"):
        params["max_q"] = model.max_q
    if hasattr(model, "max_order"):
        params["max_order"] = model.max_order

    return params


def compare_models(
    models: list,
    df: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "total_cost",
    cv_params: dict | None = None,
) -> pd.DataFrame:
    """Run cross-validation on multiple models and compare.

    Args:
        models: List of forecaster instances.
        df: Training data.
        date_col: Date column name.
        value_col: Value column name.
        cv_params: Dict with initial, horizon, step for CV.

    Returns:
        DataFrame with one row per model: [model, mape_mean, mape_std,
        rmse_mean, mae_mean, n_folds].
    """
    if cv_params is None:
        cv_params = {"initial": 60, "horizon": 14, "step": 7}

    results = []

    for model in models:
        folds = time_series_cv(
            model,
            df,
            date_col=date_col,
            value_col=value_col,
            **cv_params,
        )

        if len(folds) == 0:
            # Not enough data for CV
            results.append({
                "model": model.name,
                "mape_mean": np.nan,
                "mape_std": np.nan,
                "rmse_mean": np.nan,
                "mae_mean": np.nan,
                "n_folds": 0,
            })
        else:
            mapes = [f["mape"] for f in folds]
            rmses = [f["rmse"] for f in folds]
            maes = [f["mae"] for f in folds]

            results.append({
                "model": model.name,
                "mape_mean": np.nanmean(mapes),
                "mape_std": np.nanstd(mapes),
                "rmse_mean": np.nanmean(rmses),
                "mae_mean": np.nanmean(maes),
                "n_folds": len(folds),
            })

    return pd.DataFrame(results).sort_values("mape_mean")
