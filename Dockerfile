# Smart Cloud Optimizer — Python image.
# Shared by the FastAPI backend (default CMD) and the legacy Streamlit
# dashboard (command overridden in docker-compose). WORKDIR is the repo root
# so bare `import config` / `import storage` resolve (top-level modules).
FROM python:3.12-slim

# No apt step: the pinned numeric/ML stack (numpy/scipy/pandas/statsmodels/
# pmdarima/prophet) installs from manylinux wheels that vendor their own
# OpenMP/BLAS, so no compiler or system libgomp is needed. The container
# healthchecks use Python's stdlib urllib (see docker-compose.yml) instead of
# curl. This keeps the image smaller and removes the build-time apt dependency.
WORKDIR /app

# Install Python deps first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Fail the build (not production) if the compiled numeric/ML stack has a numpy
# ABI mismatch — surfaces 'numpy.dtype size changed' at build time instead of
# on first ml_engine import. Paired with the == pins in requirements.txt.
RUN python -c "import numpy, scipy, pandas, statsmodels.api, pmdarima, prophet"

# Copy only the runtime code the app needs (honors .dockerignore).
# Verified against top-level imports in backend_api/ and app.py:
#   backend_api -> ai_module, ml_engine, optimizer, storage, config
#   app.py      -> dashboard, ai_module, ml_engine, storage, config
# aws_collector + data_generation included for the real-collection /
# synthetic-data code paths the dashboard exposes.
COPY config.py app.py ./
COPY backend_api/ ./backend_api/
COPY storage/ ./storage/
COPY ml_engine/ ./ml_engine/
COPY optimizer/ ./optimizer/
COPY ai_module/ ./ai_module/
COPY aws_collector/ ./aws_collector/
COPY dashboard/ ./dashboard/
COPY data_generation/ ./data_generation/
COPY data/ ./data/

# Run as a non-root user; give it ownership of the app tree (data/ is
# written at runtime — SQLite WAL needs a writable dir).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# No image-level HEALTHCHECK: this image is reused by both the FastAPI backend
# (:8000) and the Streamlit dashboard (:8501), which have different probes.
# Each service defines its own healthcheck in docker-compose.yml so the image
# stays port-agnostic. The probes use Python stdlib urllib (no curl in image).

CMD ["uvicorn", "backend_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
