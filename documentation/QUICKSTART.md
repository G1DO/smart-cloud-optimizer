# Quickstart

The application on `main` is the TypeScript/Next.js frontend with a FastAPI
backend. Follow the [README quick start](../README.md#quick-start) for Docker
or the two-terminal manual setup. It includes prerequisites, environment
templates, ports, and the demo sign-in flow.

Open http://localhost:3000 and choose **Try Demo Mode** to explore the existing
synthetic workspace without AWS credentials. New accounts start empty and can
connect AWS from **Account Settings → Connections**. Read the
[security limitations](../README.md#known-limitations--security-notes) before
using real account data.

- [Development](DEVELOPMENT.md): Python tests, frontend lint/build, and API reference.
- [Architecture](ARCHITECTURE.md): application boundaries and data flow.
- [Configuration](CONFIGURATION.md): shared settings and runtime behavior.
- [Startup](STARTUP.md): optional legacy Streamlit UI and engine entry points.
- [Optimizer usage](optimizer.md#usage): run against a disposable database copy.

Forecasting runs through the Forecasts page or the generated API reference at
http://localhost:8000/docs. The ML command-line entry point is a placeholder.
