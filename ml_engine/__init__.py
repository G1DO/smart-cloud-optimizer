"""ml_engine — ML training, forecasting, and data preparation.

Part of the Smart Cloud Optimizer graduation project.
"""

from .data_prep import (
    add_time_features,
    aggregate_metrics,
    create_lag_features,
    load_cost_data,
    load_dynamodb_metrics,
    load_ebs_metrics,
    load_ec2_metrics,
    load_ecs_metrics,
    load_elasticache_metrics,
    load_elb_metrics,
    load_lambda_metrics,
    load_nat_gateway_metrics,
    load_rds_metrics,
    load_s3_metrics,
    load_service_metrics,
    prepare_for_training,
)

from .anomaly import (
    detect_iqr,
    detect_zscore,
    flag_anomalies,
)

from .forecaster import (
    BaseForecaster,
    ETSForecaster,
    NaiveForecaster,
    ProphetForecaster,
    SARIMAXForecaster,
    SeasonalNaiveForecaster,
)

from .evaluator import (
    calc_metrics,
    compare_models,
    time_series_cv,
)

__all__ = [
    # Data prep
    "load_cost_data",
    "load_ec2_metrics",
    "load_rds_metrics",
    "load_elasticache_metrics",
    "load_ecs_metrics",
    "load_lambda_metrics",
    "load_dynamodb_metrics",
    "load_ebs_metrics",
    "load_s3_metrics",
    "load_nat_gateway_metrics",
    "load_elb_metrics",
    "load_service_metrics",
    "add_time_features",
    "prepare_for_training",
    "aggregate_metrics",
    "create_lag_features",
    # Anomaly detection
    "detect_zscore",
    "detect_iqr",
    "flag_anomalies",
    # Forecasters
    "BaseForecaster",
    "NaiveForecaster",
    "SeasonalNaiveForecaster",
    "ETSForecaster",
    "ProphetForecaster",
    "SARIMAXForecaster",
    # Evaluation
    "calc_metrics",
    "time_series_cv",
    "compare_models",
]
