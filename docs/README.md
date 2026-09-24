# Technical documentation

These guides describe the implemented application on **`main`**.
[README](../README.md#quick-start) owns installation and first use;
[CONTRIBUTING](../CONTRIBUTING.md) links the canonical Workflow and Documentation
guidance. [Notion](https://app.notion.com/p/28b0a821b3cc8061adebea034b7da111)
owns project intent and decisions; GitHub owns accepted work and review.

| Responsibility | Start here |
| --- | --- |
| Architecture | [System boundaries and source map](architecture/README.md), [data pipeline](architecture/data-pipeline.md), [data model](architecture/data-model.md) |
| Engine behavior | [Forecasting](architecture/engines/forecasting.md), [optimizer](architecture/engines/optimizer.md), [AI advisor](architecture/engines/ai-advisor.md) |
| Development | [Checks and conventions](development/README.md), [legacy Streamlit UI](development/streamlit.md) |
| API / contracts | [Generated HTTP reference and compatibility](api/http.md), [storage contracts and signatures](api/storage.md) |
| Operations | [Local diagnostics, persistence, and recovery](operations/local-runtime.md) |
| Security | [Trust boundaries and data handling](security/README.md), [vulnerability reporting](../SECURITY.md) |
| Reference | [Environment variables and active configuration](reference/configuration.md) |

Setup stays in README because one shared entry point covers this local stack.
Engine guides are nested under architecture because they explain the current
subsystems. Local diagnostics and recovery share one operations guide. No separate
RFC or ADR collection exists yet; add a record only for a real proposal or an
architecturally significant decision, preserving any superseded history.

## Historical material

The [thesis archive](../docs-gp/README.md) keeps academic documents, editing records,
research references, and earlier numerical observations together. The
[imported integration review](archive/imported-integration-review.md) preserves
historical engineering evidence. Neither is the active backlog or current
validation. Current verification belongs in PRs/check output; link to evidence
rather than copying pass counts into these guides.
