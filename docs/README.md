# Technical documentation

These guides describe the implemented application on **`main`**.
Start with the [README](../README.md#quick-start) for installation and first use,
or the [development guide](development/README.md) for checks and contribution
conventions.

| Responsibility | Start here |
| --- | --- |
| Architecture | [System boundaries and source map](architecture/README.md), [data pipeline](architecture/data-pipeline.md), [data model](architecture/data-model.md) |
| Engine behavior | [Forecasting](architecture/engines/forecasting.md), [optimizer](architecture/engines/optimizer.md), [AI advisor](architecture/engines/ai-advisor.md) |
| Development | [Checks and conventions](development/README.md), [legacy Streamlit UI](development/streamlit.md) |
| API / contracts | [Generated HTTP reference and compatibility](api/http.md), [storage contracts and signatures](api/storage.md) |
| Operations | [Local diagnostics, persistence, and recovery](operations/local-runtime.md) |
| Security | [Trust boundaries and data handling](security/README.md), [vulnerability reporting](../SECURITY.md) |
| Reference | [Environment variables and active configuration](reference/configuration.md) |

## Project report

[Project report (PDF)](project-report.pdf) is exported from the latest corrected
graduation report. It records the project at the time it was written; use the
guides above for current application behavior.
