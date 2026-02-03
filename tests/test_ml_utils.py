"""Tests for ml_engine.data_prep — DB-backed data loading and ML prep."""
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
