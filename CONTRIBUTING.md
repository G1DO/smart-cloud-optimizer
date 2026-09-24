# Contributing

Application changes target **`main`**, which contains the TypeScript/Next.js UI,
FastAPI backend, and shared Python engines. `release/ccpe-v1.0` is the separate
paper artifact and is currently GitHub's default branch; select `main` explicitly
when opening an application PR.

The canonical [Workflow](https://app.notion.com/p/3bb0a821b3cc817394cdf93a936a3612)
defines engineering flow. The canonical
[Documentation guidance](https://app.notion.com/p/3bb0a821b3cc815099acfd2d5e8b0859)
defines documentation responsibilities. Keep product context and decisions in
Notion, execution and review in GitHub, and durable implementation details in
this repository. Update affected technical docs in the same PR as code changes.

Start with the [README setup](README.md#quick-start), then use the
[development guide](docs/development/README.md) for checks and conventions and
the [documentation index](docs/README.md) to find technical references.
Keep PRs focused and describe the behavior changed, the reason, and verification
actually run. Record existing failures separately from regressions.

There are currently no repository CI workflows or prescribed PR/issue templates.
Run the relevant local checks and report their results in the PR. Respect any
review or protection requirements configured on the target branch at merge time.

Use temporary databases and mocked AWS/AI services for verification. Never add
credentials, personal data, or runtime database changes to a PR. The existing
demo database has known data and security limitations documented in the
[security guide](docs/security/README.md).
Do not post undisclosed sensitive vulnerability details in public issues or PRs.

For vulnerability reporting, use [SECURITY.md](SECURITY.md).
