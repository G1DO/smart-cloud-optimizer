"""Time series forecasters for cost prediction.

All forecasters follow the same interface:
    forecaster.fit(df)
    predictions = forecaster.predict(horizon=30)

Predictions DataFrame has columns: [date, forecast, lower, upper]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
import hashlib
import warnings

import numpy as np
import pandas as pd


def _series_signature(df: pd.DataFrame) -> str:
    """Create a lightweight stable signature for cache / fit tracking."""
    if df.empty:
        return "empty"

    payload = (
        df["date"].astype(str).str.cat(sep="|")
        + "||"
        + df["value"].round(6).astype(str).str.cat(sep="|")
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


class BaseForecaster(ABC):
    """Abstract base class for all forecasters."""

    name: str = "base"

    def __init__(self):
        self._fitted = False
        self._last_date = None
        self._last_value = None
        self._history = None
        self._signature = None

    @abstractmethod
    def fit(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        value_col: str = "total_cost",
    ) -> "BaseForecaster":
        pass

    @abstractmethod
    def predict(self, horizon: int = 30) -> pd.DataFrame:
        pass

    def _validate_fitted(self):
        if not self._fitted:
            raise RuntimeError(f"{self.name} must be fit before predict")

    def _prepare_data(
        self,
        df: pd.DataFrame,
        date_col: str,
        value_col: str,
    ) -> pd.DataFrame:
        data = df[[date_col, value_col]].copy()
        data.columns = ["date", "value"]
        data["date"] = pd.to_datetime(data["date"])
        data = data.sort_values("date").reset_index(drop=True)
        return data


class NaiveForecaster(BaseForecaster):
    """Naive baseline: repeat last observed value."""

    name = "Naive"

    def fit(self, df, date_col="date", value_col="total_cost"):
        data = self._prepare_data(df, date_col, value_col)
        self._last_date = data["date"].iloc[-1]
        self._last_value = float(data["value"].iloc[-1])
        self._std = float(data["value"].std() or 0.0)
        self._signature = _series_signature(data)
        self._fitted = True
        return self

    def predict(self, horizon=30):
        self._validate_fitted()

        dates = [self._last_date + timedelta(days=i + 1) for i in range(horizon)]
        forecasts = np.full(horizon, self._last_value, dtype=float)
        lower = forecasts - 1.96 * self._std
        upper = forecasts + 1.96 * self._std

        return pd.DataFrame(
            {
                "date": dates,
                "forecast": forecasts,
                "lower": lower,
                "upper": upper,
            }
        )


class SeasonalNaiveForecaster(BaseForecaster):
    """Seasonal naive baseline: repeat previous seasonal values."""

    name = "Seasonal Naive"

    def __init__(self, season_length=7):
        super().__init__()
        self.season_length = season_length

    def fit(self, df, date_col="date", value_col="total_cost"):
        data = self._prepare_data(df, date_col, value_col)
        self._last_date = data["date"].iloc[-1]
        self._history = data["value"].astype(float).values
        self._std = float(data["value"].std() or 0.0)
        self._signature = _series_signature(data)
        self._fitted = True
        return self

    def predict(self, horizon=30):
        self._validate_fitted()

        if len(self._history) == 0:
            raise RuntimeError("No history available for seasonal naive prediction")

        dates = []
        forecasts = []

        for i in range(horizon):
          dates.append(self._last_date + timedelta(days=i + 1))
          seasonal_index = len(self._history) - self.season_length + (i % self.season_length)

          if seasonal_index < 0:
              seasonal_index = i % len(self._history)

          forecasts.append(float(self._history[seasonal_index]))

        forecasts = np.asarray(forecasts, dtype=float)
        lower = forecasts - 1.96 * self._std
        upper = forecasts + 1.96 * self._std

        return pd.DataFrame(
            {
                "date": dates,
                "forecast": forecasts,
                "lower": lower,
                "upper": upper,
            }
        )


class ETSForecaster(BaseForecaster):
    """Exponential smoothing forecaster."""

    name = "ETS"

    def __init__(self, seasonal_periods=7, trend="add", seasonal="add"):
        super().__init__()
        self.seasonal_periods = seasonal_periods
        self.trend = trend
        self.seasonal = seasonal
        self._model = None
        self._fit_result = None

    def fit(self, df, date_col="date", value_col="total_cost"):
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        data = self._prepare_data(df, date_col, value_col)
        self._last_date = data["date"].iloc[-1]
        values = data["value"].astype(float).values
        self._signature = _series_signature(data)

        if len(values) < max(14, 2 * self.seasonal_periods):
            self._model = ExponentialSmoothing(values, trend=self.trend, seasonal=None)
        else:
            self._model = ExponentialSmoothing(
                values,
                trend=self.trend,
                seasonal=self.seasonal,
                seasonal_periods=self.seasonal_periods,
            )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._fit_result = self._model.fit(optimized=True)

        self._fitted = True
        return self

    def predict(self, horizon=30):
        self._validate_fitted()

        forecast = self._fit_result.forecast(horizon)
        forecast_values = np.asarray(forecast, dtype=float)
        dates = [self._last_date + timedelta(days=i + 1) for i in range(horizon)]

        residuals = getattr(self._fit_result, "resid", None)
        if residuals is not None and len(residuals) > 0:
            std = float(np.std(residuals))
        else:
            std = float(np.std(forecast_values) or 0.0)

        return pd.DataFrame(
            {
                "date": dates,
                "forecast": forecast_values,
                "lower": forecast_values - 1.96 * std,
                "upper": forecast_values + 1.96 * std,
            }
        )


class ProphetForecaster(BaseForecaster):
    """Facebook Prophet / Prophet forecaster."""

    name = "Prophet"

    def __init__(
        self,
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
    ):
        super().__init__()
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.changepoint_prior_scale = changepoint_prior_scale
        self._model = None

    def fit(self, df, date_col="date", value_col="total_cost"):
        from prophet import Prophet

        data = self._prepare_data(df, date_col, value_col)
        self._last_date = data["date"].iloc[-1]
        self._signature = _series_signature(data)

        prophet_df = data.rename(columns={"date": "ds", "value": "y"})

        self._model = Prophet(
            yearly_seasonality=self.yearly_seasonality,
            weekly_seasonality=self.weekly_seasonality,
            daily_seasonality=self.daily_seasonality,
            changepoint_prior_scale=self.changepoint_prior_scale,
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._model.fit(prophet_df)

        self._fitted = True
        return self

    def predict(self, horizon=30):
        self._validate_fitted()

        future = self._model.make_future_dataframe(periods=horizon)
        forecast = self._model.predict(future).tail(horizon)

        return pd.DataFrame(
            {
                "date": forecast["ds"].values,
                "forecast": forecast["yhat"].values.astype(float),
                "lower": forecast["yhat_lower"].values.astype(float),
                "upper": forecast["yhat_upper"].values.astype(float),
            }
        )


class SARIMAXForecaster(BaseForecaster):
    """Auto-ARIMA / SARIMAX style forecaster."""

    name = "SARIMAX"

    def __init__(self, seasonal_period=7, max_p=2, max_q=2, max_order=4):
        super().__init__()
        self.seasonal_period = seasonal_period
        self.max_p = max_p
        self.max_q = max_q
        self.max_order = max_order
        self._model = None

    def fit(self, df, date_col="date", value_col="total_cost"):
        import pmdarima as pm

        data = self._prepare_data(df, date_col, value_col)
        self._last_date = data["date"].iloc[-1]
        values = data["value"].astype(float).values
        self._signature = _series_signature(data)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._model = pm.auto_arima(
                values,
                seasonal=True,
                m=self.seasonal_period,
                start_p=0,
                start_q=0,
                max_p=self.max_p,
                max_q=self.max_q,
                max_order=self.max_order,
                d=None,
                D=1,
                stepwise=True,
                suppress_warnings=True,
                error_action="ignore",
                n_fits=20,
            )

        self._fitted = True
        return self

    def predict(self, horizon=30):
        self._validate_fitted()

        forecast, conf_int = self._model.predict(
            n_periods=horizon,
            return_conf_int=True,
        )
        dates = [self._last_date + timedelta(days=i + 1) for i in range(horizon)]

        return pd.DataFrame(
            {
                "date": dates,
                "forecast": np.asarray(forecast, dtype=float),
                "lower": conf_int[:, 0].astype(float),
                "upper": conf_int[:, 1].astype(float),
            }
        )

    def get_order(self):
        self._validate_fitted()
        return self._model.order, self._model.seasonal_order


def build_forecaster(model_name: str) -> BaseForecaster:
    """Factory helper used by the API router."""
    normalized = model_name.strip()

    if normalized == "Prophet":
        return ProphetForecaster()
    if normalized == "SARIMAX":
        return SARIMAXForecaster()
    if normalized == "ETS":
        return ETSForecaster()
    if normalized == "Seasonal Naive":
        return SeasonalNaiveForecaster(season_length=7)
    if normalized == "Naive":
        return NaiveForecaster()

    raise ValueError(f"Unsupported model: {model_name}")