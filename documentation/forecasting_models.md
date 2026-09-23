# Forecasting Models

## Current application behavior

[ml_engine/forecaster.py](../ml_engine/forecaster.py) implements Naive,
Seasonal Naive, ETS, Prophet, and SARIMAX. The primary Next.js UI calls
[backend_api/routers/forecast.py](../backend_api/routers/forecast.py):

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

[ml_engine/evaluator.py](../ml_engine/evaluator.py) provides `time_series_cv()`
and `compare_models()` for expanding-window validation against held-out values.
They report MAPE, RMSE, and MAE; MAPE excludes zero actuals. These routines are
separate from the HTTP model-comparison endpoint.

For a local evaluation, load the selected workspace through
`ml_engine.data_prep.load_cost_data()`, choose explicit initial/horizon/step
parameters, and call `compare_models()` with the forecasters under test. Close
the database connection after loading. The synthetic demo workspace is
`aws-SYNTHETIC-001`. Preserve the data snapshot, parameters, code revision,
dependency versions, and output when using results to make a model decision.

Anomaly detection in [ml_engine/anomaly.py](../ml_engine/anomaly.py) combines
rolling Z-score and IQR flags by default. For offline evaluation, document any
filtering and fit preprocessing on training data so future observations do not
influence a fold's training set.

```bash
python -m pytest tests/test_ml_utils.py tests/test_frontend_backend_contract.py -v
```

## Historical evaluation notes

The following tables are retained from an earlier analysis. The original note
reported walk-forward tests with an initial 120-day window and 30-day steps,
but `main` does not contain an exact input snapshot and executable run tied to
these numbers. They are not current verified accuracy, service guarantees, or
the runtime model-selection policy. The
[paper's open questions](../docs-gp/OPEN_QUESTIONS.md) also identify older,
conflicting evaluation results. Current project conclusions belong in
[Notion project context](https://app.notion.com/p/28b0a821b3cc8061adebea034b7da111).

### Recorded horizon comparison (MAPE)

| Horizon | Naive | SeasonalNaive | ETS | Prophet | Winner |
|---------|-------|---------------|-----|---------|--------|
| 7 days | 40.5% | 16.0% | 9.2% | 7.9% | **Prophet** |
| 14 days | 22.9% | 17.9% | 10.5% | 9.8% | **Prophet** |
| 30 days | 25.7% | 14.6% | 10.4% | 9.5% | **Prophet** |
| 60 days | 25.5% | 14.9% | 10.8% | 22.2% | **ETS** |
| 90 days | 25.8% | 13.1% | 12.0% | 12.4% | **ETS** |
| 120 days | 32.0% | 15.7% | 13.0% | 34.5% | **ETS** |
| 180 days | 43.1% | 16.0% | 12.9% | 27.9% | **ETS** |
| 240 days | 30.9% | 22.7% | 20.6% | 26.8% | **ETS** |
| 300 days | 32.2% | 16.8% | 24.0% | 34.1% | **SeasonalNaive** |

### Recorded training-size comparison (30-day forecast MAPE)

| Training Data | Naive | SNaive | ETS | Prophet | Winner |
|---------------|-------|--------|-----|---------|--------|
| 7 days | 29.8% | **14.0%** | 297% | 1015% | **SNaive** |
| 14 days | 24.6% | **10.1%** | 22.8% | 1176% | **SNaive** |
| 1 month | 32.1% | **9.3%** | 12.9% | 46.7% | **SNaive** |
| 2 months | 42.5% | 10.3% | **9.7%** | 1552% | **ETS** |
| 3 months | 42.0% | 17.0% | **12.0%** | 968% | **ETS** |
| 6 months | 25.4% | 14.6% | **11.1%** | 16.8% | **ETS** |
| 1 year | 25.9% | 16.0% | **12.4%** | 14.9% | **ETS** |
| 14 months | 24.4% | 20.6% | **18.5%** | 19.4% | **ETS** |
| 1.5 years | 35.7% | 12.4% | **10.9%** | 12.2% | **ETS** |
