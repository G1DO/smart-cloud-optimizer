# Forecasting Models

## Current application behavior

[ml_engine/forecaster.py](../../../ml_engine/forecaster.py) implements Naive,
Seasonal Naive, ETS, Prophet, and SARIMAX. The primary Next.js UI calls
[backend_api/routers/forecast.py](../../../backend_api/routers/forecast.py):

- `GET /api/forecast` defaults to Prophet and a 30-day horizon. It accepts
  horizons of 1–180 days and requires at least 30 normalized daily observations.
- The router loads the latest 365 stored daily observations.
  It applies anomaly filtering, retaining the original series if filtering
  leaves fewer than 30 observations.
- `GET /api/forecast/compare` runs the five models and compares forecast spend
  with the historical daily average. `vs_historical_pct` is not prediction
  accuracy, MAPE, or walk-forward validation. A failed model produces null
  forecast values in the comparison response.
- Responses are cached in process by user, horizon, series fingerprint, and
  model where applicable. These HTTP routes do not save forecasts to SQLite.
  The legacy Streamlit page runs models directly and offers CSV export; it
  also does not save forecasts to SQLite.

There is no automatic data-age-based model selection in the HTTP router.
Use the running backend's generated http://localhost:8000/docs for the current
HTTP contract. The CLI remains a placeholder; use the UI or Python API.

## Reproducible evaluation

[ml_engine/evaluator.py](../../../ml_engine/evaluator.py) provides `time_series_cv()`
and `compare_models()` for expanding-window validation against held-out values.
They report MAPE, RMSE, and MAE; MAPE excludes zero actuals. These routines are
separate from the HTTP model-comparison endpoint.

For a local evaluation, load the selected workspace through
`ml_engine.data_prep.load_cost_data()`, choose explicit initial/horizon/step
parameters, and call `compare_models()` with the forecasters under test. Close
the database connection after loading. The synthetic demo workspace is
`aws-SYNTHETIC-001`. Preserve the data snapshot, parameters, code revision,
dependency versions, and output when using results to make a model decision.

Anomaly detection in [ml_engine/anomaly.py](../../../ml_engine/anomaly.py) combines
rolling Z-score and IQR flags by default. For offline evaluation, document any
filtering and fit preprocessing on training data so future observations do not
influence a fold's training set.

```bash
python -m pytest tests/test_ml_utils.py tests/test_frontend_backend_contract.py -v
```
