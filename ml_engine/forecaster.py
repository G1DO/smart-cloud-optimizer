"""Time series forecasters for cost prediction.

All forecasters follow the same interface:
    forecaster.fit(df)
    predictions = forecaster.predict(horizon=30)

Predictions DataFrame has columns: [date, forecast, lower, upper]
"""

from abc import ABC, abstractmethod
from datetime import timedelta
import warnings

import numpy as np
import pandas as pd


class BaseForecaster(ABC):
    """Abstract base class for all forecasters."""

    name: str = "base"

    def __init__(self):
        self._fitted = False
        self._last_date = None
        self._last_value = None
        self._history = None

    @abstractmethod
    def fit(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        value_col: str = "total_cost",
    ) -> "BaseForecaster":
        """Fit the model on historical data.

        Args:
            df: DataFrame with date and value columns.
            date_col: Name of date column.
            value_col: Name of value column.

        Returns:
            self for chaining.
        """
        pass

    @abstractmethod
    def predict(self, horizon: int = 30) -> pd.DataFrame:
        """Generate forecast for future dates.

        Args:
            horizon: Number of days to forecast.

        Returns:
            DataFrame with columns [date, forecast, lower, upper].
        """
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
        """Standardize input data."""
        data = df[[date_col, value_col]].copy()
        data.columns = ["date", "value"]
        data["date"] = pd.to_datetime(data["date"])
        data = data.sort_values("date").reset_index(drop=True)
        return data


class NaiveForecaster(BaseForecaster):
    """Naive baseline: repeat last observed value.

    Useful as a sanity check — if your fancy model can't beat this,
    something is wrong.
    """

    name = "Naive"

    def fit(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        value_col: str = "total_cost",
    ) -> "NaiveForecaster":
        data = self._prepare_data(df, date_col, value_col)
        self._last_date = data["date"].iloc[-1]
        self._last_value = data["value"].iloc[-1]
        self._std = data["value"].std()
        self._fitted = True
        return self

    def predict(self, horizon: int = 30) -> pd.DataFrame:
        self._validate_fitted()

        dates = [self._last_date + timedelta(days=i + 1) for i in range(horizon)]

        return pd.DataFrame({
            "date": dates,
            "forecast": [self._last_value] * horizon,
            "lower": [self._last_value - 1.96 * self._std] * horizon,
            "upper": [self._last_value + 1.96 * self._std] * horizon,
        })


class SeasonalNaiveForecaster(BaseForecaster):
    """Seasonal naive: use value from same day last week.

    Captures weekly patterns without any model complexity.
    """

    name = "SeasonalNaive"

    def __init__(self, season_length: int = 7):
        super().__init__()
        self.season_length = season_length

    def fit(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        value_col: str = "total_cost",
    ) -> "SeasonalNaiveForecaster":
        data = self._prepare_data(df, date_col, value_col)
        self._last_date = data["date"].iloc[-1]
        self._history = data["value"].values
        self._std = data["value"].std()
        self._fitted = True
        return self

    def predict(self, horizon: int = 30) -> pd.DataFrame:
        self._validate_fitted()

        dates = []
        forecasts = []

        for i in range(horizon):
            dates.append(self._last_date + timedelta(days=i + 1))
            # Use value from season_length days ago (cyclically)
            idx = -(self.season_length - (i % self.season_length))
            forecasts.append(self._history[idx])

        return pd.DataFrame({
            "date": dates,
            "forecast": forecasts,
            "lower": [f - 1.96 * self._std for f in forecasts],
            "upper": [f + 1.96 * self._std for f in forecasts],
        })


class ETSForecaster(BaseForecaster):
    """Exponential Smoothing (ETS) model.

    Handles trend and seasonality via statsmodels ExponentialSmoothing.
    """

    name = "ETS"

    def __init__(
        self,
        seasonal_periods: int = 7,
        trend: str = "add",
        seasonal: str = "add",
    ):
        super().__init__()
        self.seasonal_periods = seasonal_periods
        self.trend = trend
        self.seasonal = seasonal
        self._model = None
        self._fit_result = None

    def fit(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        value_col: str = "total_cost",
    ) -> "ETSForecaster":
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        data = self._prepare_data(df, date_col, value_col)
        self._last_date = data["date"].iloc[-1]
        values = data["value"].values

        # Need at least 2 full seasons for seasonal model
        if len(values) < 2 * self.seasonal_periods:
            # Fall back to simple exponential smoothing
            self._model = ExponentialSmoothing(
                values,
                trend=self.trend,
                seasonal=None,
            )
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

    def predict(self, horizon: int = 30) -> pd.DataFrame:
        self._validate_fitted()

        forecast = self._fit_result.forecast(horizon)
        forecast_values = np.asarray(forecast)
        dates = [self._last_date + timedelta(days=i + 1) for i in range(horizon)]

        # ETS doesn't give confidence intervals directly, estimate from residuals
        residuals = self._fit_result.resid
        std = np.std(residuals) if len(residuals) > 0 else np.std(forecast_values)

        return pd.DataFrame({
            "date": dates,
            "forecast": forecast_values,
            "lower": forecast_values - 1.96 * std,
            "upper": forecast_values + 1.96 * std,
        })


class ProphetForecaster(BaseForecaster):
    """Facebook Prophet model.

    Good at handling multiple seasonalities and holidays.
    """

    name = "Prophet"

    def __init__(
        self,
        yearly_seasonality: bool = True,
        weekly_seasonality: bool = True,
        daily_seasonality: bool = False,
    ):
        super().__init__()
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self._model = None

    def fit(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        value_col: str = "total_cost",
    ) -> "ProphetForecaster":
        from prophet import Prophet

        data = self._prepare_data(df, date_col, value_col)
        self._last_date = data["date"].iloc[-1]

        # Prophet expects columns named 'ds' and 'y'
        prophet_df = data.rename(columns={"date": "ds", "value": "y"})

        self._model = Prophet(
            yearly_seasonality=self.yearly_seasonality,
            weekly_seasonality=self.weekly_seasonality,
            daily_seasonality=self.daily_seasonality,
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._model.fit(prophet_df)

        self._fitted = True
        return self

    def predict(self, horizon: int = 30) -> pd.DataFrame:
        self._validate_fitted()

        future = self._model.make_future_dataframe(periods=horizon)
        forecast = self._model.predict(future)

        # Get only the forecast period (last `horizon` rows)
        forecast = forecast.tail(horizon)

        return pd.DataFrame({
            "date": forecast["ds"].values,
            "forecast": forecast["yhat"].values,
            "lower": forecast["yhat_lower"].values,
            "upper": forecast["yhat_upper"].values,
        })

    def get_components(self) -> dict:
        """Get decomposed components (trend, weekly, yearly)."""
        self._validate_fitted()
        future = self._model.make_future_dataframe(periods=0)
        forecast = self._model.predict(future)
        return {
            "trend": forecast["trend"].values,
            "weekly": forecast.get("weekly", pd.Series([0])).values,
            "yearly": forecast.get("yearly", pd.Series([0])).values,
        }


class SARIMAXForecaster(BaseForecaster):
    """SARIMAX model with auto-tuned parameters.

    Uses pmdarima's auto_arima to find best (p,d,q)(P,D,Q,m) orders.
    """

    name = "SARIMAX"

    def __init__(
        self,
        seasonal_period: int = 7,
        max_p: int = 3,
        max_q: int = 3,
        max_order: int = 6,
    ):
        super().__init__()
        self.seasonal_period = seasonal_period
        self.max_p = max_p
        self.max_q = max_q
        self.max_order = max_order
        self._model = None

    def fit(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        value_col: str = "total_cost",
    ) -> "SARIMAXForecaster":
        import pmdarima as pm

        data = self._prepare_data(df, date_col, value_col)
        self._last_date = data["date"].iloc[-1]
        values = data["value"].values

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._model = pm.auto_arima(
                values,
                seasonal=True,
                m=self.seasonal_period,
                max_p=self.max_p,
                max_q=self.max_q,
                max_order=self.max_order,
                suppress_warnings=True,
                error_action="ignore",
                stepwise=True,
            )

        self._fitted = True
        return self

    def predict(self, horizon: int = 30) -> pd.DataFrame:
        self._validate_fitted()

        forecast, conf_int = self._model.predict(
            n_periods=horizon,
            return_conf_int=True,
        )

        dates = [self._last_date + timedelta(days=i + 1) for i in range(horizon)]

        return pd.DataFrame({
            "date": dates,
            "forecast": forecast,
            "lower": conf_int[:, 0],
            "upper": conf_int[:, 1],
        })

    def get_order(self) -> tuple:
        """Get the auto-selected ARIMA order."""
        self._validate_fitted()
        return self._model.order, self._model.seasonal_order
