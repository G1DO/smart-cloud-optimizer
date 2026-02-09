"""Tests for ml_engine — data prep, anomaly detection, forecasters, evaluation."""
import numpy as np
import pandas as pd
import pytest

from storage.db import (
    create_schema,
    ensure_user,
    get_connection,
    insert_daily_costs,
    insert_ec2_instances,
    insert_ec2_metrics,
    insert_rds_instances,
    insert_rds_metrics,
)
from ml_engine.data_prep import (
    load_cost_data,
    load_ec2_metrics,
    load_rds_metrics,
    add_time_features,
    prepare_for_training,
    create_lag_features,
)
from ml_engine.anomaly import detect_zscore, detect_iqr, flag_anomalies
from ml_engine.forecaster import (
    NaiveForecaster,
    SeasonalNaiveForecaster,
    ETSForecaster,
)
from ml_engine.evaluator import calc_metrics, time_series_cv, compare_models


@pytest.fixture
def db_conn(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    create_schema(conn)
    return conn


@pytest.fixture
def user_id(db_conn):
    return ensure_user(db_conn, "TEST-ML")


class TestLoadCostData:
    def test_loads_from_db(self, db_conn, user_id):
        insert_daily_costs(db_conn, user_id, [
            {"date": "2024-01-01", "total_cost": 10.5},
            {"date": "2024-01-02", "total_cost": 20.0},
        ])
        db_conn.commit()
        df = load_cost_data(db_conn, user_id)
        assert len(df) == 2
        assert df["total_cost"].sum() == 30.5

    def test_empty_returns_empty_df(self, db_conn, user_id):
        df = load_cost_data(db_conn, user_id)
        assert len(df) == 0
        assert "date" in df.columns

    def test_date_filter(self, db_conn, user_id):
        insert_daily_costs(db_conn, user_id, [
            {"date": "2024-01-01", "total_cost": 10.0},
            {"date": "2024-02-01", "total_cost": 20.0},
        ])
        db_conn.commit()
        df = load_cost_data(db_conn, user_id, start_date="2024-01-15")
        assert len(df) == 1


class TestLoadEC2Metrics:
    def test_loads_from_db(self, db_conn, user_id):
        insert_ec2_instances(db_conn, user_id, [
            {"instance_id": "i-abc", "instance_type": "t3.micro",
             "state": "running", "launch_date": "2024-01-01", "region": "us-east-1"},
        ])
        insert_ec2_metrics(db_conn, user_id, [
            {"timestamp": "2024-01-01T00:00:00+00:00", "instance_id": "i-abc",
             "cpu_utilization": 25.0},
        ])
        db_conn.commit()
        df = load_ec2_metrics(db_conn, user_id)
        assert len(df) == 1
        assert df["cpu_utilization"].iloc[0] == 25.0

    def test_empty_returns_empty_df(self, db_conn, user_id):
        df = load_ec2_metrics(db_conn, user_id)
        assert len(df) == 0


class TestLoadRDSMetrics:
    def test_loads_from_db(self, db_conn, user_id):
        insert_rds_instances(db_conn, user_id, [
            {"db_instance_id": "prod-pg", "db_instance_class": "db.r5.large",
             "engine": "postgres", "storage_gb": 100},
        ])
        insert_rds_metrics(db_conn, user_id, [
            {"timestamp": "2024-01-01T00:00:00+00:00", "db_instance_id": "prod-pg",
             "cpu_utilization": 15.0},
        ])
        db_conn.commit()
        df = load_rds_metrics(db_conn, user_id)
        assert len(df) == 1

    def test_empty_returns_empty_df(self, db_conn, user_id):
        df = load_rds_metrics(db_conn, user_id)
        assert len(df) == 0


class TestAddTimeFeatures:
    def test_adds_features(self, db_conn, user_id):
        import pandas as pd
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01 10:00:00", "2024-01-02 14:00:00"]),
            "value": [1.0, 2.0],
        })
        result = add_time_features(df)
        assert "hour" in result.columns
        assert "is_weekend" in result.columns
        assert "hour_sin" in result.columns
        assert result["hour"].iloc[0] == 10

    def test_missing_timestamp_noop(self):
        import pandas as pd
        df = pd.DataFrame({"value": [1, 2]})
        result = add_time_features(df)
        assert list(result.columns) == ["value"]


class TestPrepareForTraining:
    def test_splits_x_y(self):
        import pandas as pd
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02"],
            "user_id": ["u1", "u1"],
            "cpu": [10.0, 20.0],
            "cost": [5.0, 10.0],
        })
        X, y = prepare_for_training(df, "cost")
        assert "cpu" in X.columns
        assert "timestamp" not in X.columns
        assert "user_id" not in X.columns
        assert len(y) == 2


class TestCreateLagFeatures:
    def test_creates_lags(self):
        import pandas as pd
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="D"),
            "value": range(10),
        })
        result = create_lag_features(df, ["value"], lags=[1, 3])
        assert "value_lag_1" in result.columns
        assert "value_lag_3" in result.columns


# ── Fixtures for forecasting tests ──────────────────────────────────

@pytest.fixture
def cost_df():
    """60 days of cost data with a weekly pattern."""
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    # Base cost + weekly pattern (weekends cheaper)
    base = 100.0
    values = [base + 20 * np.sin(2 * np.pi * i / 7) for i in range(60)]
    return pd.DataFrame({"date": dates, "total_cost": values})


@pytest.fixture
def cost_df_short():
    """10 days — too short for seasonal ETS."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame({
        "date": dates,
        "total_cost": [100 + i for i in range(10)],
    })


# ── Anomaly Detection ───────────────────────────────────────────────

class TestDetectZscore:
    def test_clean_data_no_anomalies(self):
        series = pd.Series([10.0] * 50)
        result = detect_zscore(series, window=10, threshold=3.0)
        assert result.sum() == 0

    def test_spike_flagged(self):
        values = [10.0] * 50
        values[25] = 1000.0  # obvious spike
        series = pd.Series(values)
        # window=30 so the spike has less influence on its own rolling mean/std
        result = detect_zscore(series, window=30, threshold=3.0)
        assert result[25] is np.True_

    def test_constant_values_no_crash(self):
        # std = 0 → should not crash, should not flag
        series = pd.Series([5.0] * 30)
        result = detect_zscore(series, window=10, threshold=3.0)
        assert result.sum() == 0


class TestDetectIqr:
    def test_clean_data_no_anomalies(self):
        series = pd.Series(np.random.normal(100, 5, size=100))
        result = detect_iqr(series, multiplier=3.0)  # wide bounds
        assert result.sum() == 0

    def test_outlier_detected(self):
        values = [10.0] * 100
        values[50] = 10000.0
        series = pd.Series(values)
        result = detect_iqr(series, multiplier=1.5)
        assert result[50] is np.True_


class TestFlagAnomalies:
    def test_adds_is_anomaly_column(self):
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=50),
            "total_cost": [10.0] * 50,
        })
        result = flag_anomalies(df, "total_cost")
        assert "is_anomaly" in result.columns
        assert result["is_anomaly"].sum() == 0

    def test_union_of_methods(self):
        values = [10.0] * 50
        values[25] = 1000.0
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=50),
            "total_cost": values,
        })
        result = flag_anomalies(df, "total_cost")
        assert result["is_anomaly"].iloc[25]

    def test_original_df_unchanged(self):
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10),
            "total_cost": [10.0] * 10,
        })
        flag_anomalies(df, "total_cost")
        assert "is_anomaly" not in df.columns


# ── Forecasters ─────────────────────────────────────────────────────

class TestNaiveForecaster:
    def test_predict_returns_correct_shape(self, cost_df):
        model = NaiveForecaster()
        model.fit(cost_df)
        pred = model.predict(horizon=14)
        assert len(pred) == 14
        assert list(pred.columns) == ["date", "forecast", "lower", "upper"]

    def test_forecast_equals_last_value(self, cost_df):
        model = NaiveForecaster()
        model.fit(cost_df)
        pred = model.predict(horizon=5)
        last_value = cost_df["total_cost"].iloc[-1]
        assert all(pred["forecast"] == last_value)

    def test_raises_if_not_fitted(self):
        model = NaiveForecaster()
        with pytest.raises(RuntimeError, match="must be fit"):
            model.predict(horizon=7)

    def test_lower_less_than_upper(self, cost_df):
        model = NaiveForecaster()
        model.fit(cost_df)
        pred = model.predict(horizon=7)
        assert all(pred["lower"] < pred["upper"])


class TestSeasonalNaiveForecaster:
    def test_predict_returns_correct_shape(self, cost_df):
        model = SeasonalNaiveForecaster(season_length=7)
        model.fit(cost_df)
        pred = model.predict(horizon=14)
        assert len(pred) == 14
        assert list(pred.columns) == ["date", "forecast", "lower", "upper"]

    def test_weekly_pattern_repeats(self, cost_df):
        model = SeasonalNaiveForecaster(season_length=7)
        model.fit(cost_df)
        pred = model.predict(horizon=14)
        # Days 0-6 should equal days 7-13 (same weekly cycle)
        first_week = pred["forecast"].iloc[:7].values
        second_week = pred["forecast"].iloc[7:14].values
        np.testing.assert_array_equal(first_week, second_week)

    def test_raises_if_not_fitted(self):
        model = SeasonalNaiveForecaster()
        with pytest.raises(RuntimeError, match="must be fit"):
            model.predict(horizon=7)


class TestETSForecaster:
    def test_predict_returns_correct_shape(self, cost_df):
        model = ETSForecaster(seasonal_periods=7)
        model.fit(cost_df)
        pred = model.predict(horizon=14)
        assert len(pred) == 14
        assert list(pred.columns) == ["date", "forecast", "lower", "upper"]

    def test_fallback_with_short_data(self, cost_df_short):
        # < 2 * seasonal_periods → falls back to non-seasonal
        model = ETSForecaster(seasonal_periods=7)
        model.fit(cost_df_short)
        pred = model.predict(horizon=7)
        assert len(pred) == 7

    def test_lower_less_than_upper(self, cost_df):
        model = ETSForecaster(seasonal_periods=7)
        model.fit(cost_df)
        pred = model.predict(horizon=7)
        assert all(pred["lower"] < pred["upper"])


# ── Evaluator ───────────────────────────────────────────────────────

class TestCalcMetrics:
    def test_perfect_prediction(self):
        y = np.array([10.0, 20.0, 30.0])
        metrics = calc_metrics(y, y)
        assert metrics["mape"] == 0.0
        assert metrics["rmse"] == 0.0
        assert metrics["mae"] == 0.0

    def test_known_values(self):
        y_true = np.array([100.0, 200.0])
        y_pred = np.array([110.0, 180.0])
        metrics = calc_metrics(y_true, y_pred)
        # MAPE: (|10/100| + |20/200|) / 2 * 100 = (0.1 + 0.1) / 2 * 100 = 10%
        assert abs(metrics["mape"] - 10.0) < 0.01

    def test_handles_zero_in_true(self):
        y_true = np.array([0.0, 100.0])
        y_pred = np.array([5.0, 110.0])
        metrics = calc_metrics(y_true, y_pred)
        # MAPE only uses non-zero true values
        assert not np.isnan(metrics["mape"])

    def test_returns_all_keys(self):
        metrics = calc_metrics(np.array([1.0]), np.array([2.0]))
        assert set(metrics.keys()) == {"mape", "rmse", "mae"}


class TestTimeSeriesCV:
    def test_returns_correct_folds(self, cost_df):
        model = NaiveForecaster()
        results = time_series_cv(model, cost_df, initial=30, horizon=7, step=7)
        # 60 days, initial=30, step=7 → folds at cutoff 30,37,44,51 (need cutoff+7<=60)
        expected_folds = len(range(30, 60 - 7 + 1, 7))
        assert len(results) == expected_folds

    def test_fold_has_expected_keys(self, cost_df):
        model = NaiveForecaster()
        results = time_series_cv(model, cost_df, initial=30, horizon=7, step=7)
        assert len(results) > 0
        fold = results[0]
        assert set(fold.keys()) == {"fold", "train_size", "mape", "rmse", "mae"}

    def test_not_enough_data_returns_empty(self, cost_df_short):
        model = NaiveForecaster()
        results = time_series_cv(model, cost_df_short, initial=20, horizon=7, step=7)
        assert results == []


class TestCompareModels:
    def test_returns_sorted_dataframe(self, cost_df):
        models = [NaiveForecaster(), SeasonalNaiveForecaster(season_length=7)]
        result = compare_models(
            models, cost_df,
            cv_params={"initial": 30, "horizon": 7, "step": 7},
        )
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "model" in result.columns
        assert "mape_mean" in result.columns
        # Sorted by mape_mean
        assert result["mape_mean"].iloc[0] <= result["mape_mean"].iloc[1]

    def test_expected_columns(self, cost_df):
        models = [NaiveForecaster()]
        result = compare_models(
            models, cost_df,
            cv_params={"initial": 30, "horizon": 7, "step": 7},
        )
        expected_cols = {"model", "mape_mean", "mape_std", "rmse_mean", "mae_mean", "n_folds"}
        assert set(result.columns) == expected_cols
