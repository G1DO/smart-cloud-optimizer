import logging
import uuid
from contextlib import asynccontextmanager

from cloud_optimizer.config import setup_logging
from cloud_optimizer.logging_json import set_trace_id

setup_logging(service="backend_api")
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend_api.routers.costs import router as costs_router
from backend_api.routers.dashboard import router as dashboard_router
from backend_api.routers.forecast import router as forecast_router
from backend_api.routers.recommendations import router as recommendations_router
from backend_api.routers.auth import router as auth_router
from backend_api.routers.settings import router as settings_router
from backend_api.routers.on_boarding import router as onboarding_router
from backend_api.routers.connections import router as connections_router

from storage.db import get_connection, ensure_schema, ensure_user


def _trace_id_from_request(request: Request) -> str:
    """W3C traceparent trace-id where propagated, else request id, else new id.

    Starter §Service standards Logging: trace/span IDs (W3C traceparent
    where propagated, else env correlation IDs).
    """
    traceparent = request.headers.get("traceparent", "")
    parts = traceparent.split("-")
    # W3C: version-traceid-spanid-flags; trace-id is 32 lowercase hex chars.
    if len(parts) == 4 and len(parts[1]) == 32:
        try:
            int(parts[1], 16)
            return parts[1]
        except ValueError:
            pass
    incoming = request.headers.get("x-request-id", "").strip()
    if incoming:
        return incoming[:64]
    return uuid.uuid4().hex


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_connection()
    try:
        ensure_schema(conn)
        # نضمن وجود synthetic demo user
        ensure_user(conn, "SYNTHETIC-001")
    finally:
        conn.close()
    yield


app = FastAPI(
    title="Smart Cloud Optimizer API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    # Auth is localStorage + query param, not cookies; flip back to True only when real cookie sessions are introduced.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    trace_id = _trace_id_from_request(request)
    set_trace_id(trace_id)
    logger.info(f"{request.method} {request.url.path}")
    try:
        response = await call_next(request)
    finally:
        # Reset to env default so the contextvar never leaks across requests.
        set_trace_id("")
    response.headers["X-Request-ID"] = trace_id
    return response

app.include_router(dashboard_router)
app.include_router(forecast_router)
app.include_router(costs_router)
app.include_router(recommendations_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(onboarding_router)
app.include_router(connections_router)


@app.get("/")
def root():
    return {"message": "FastAPI backend is running successfully"}


@app.get("/health")
def health():
    """Liveness: cheap, no dependency checks. When to restart."""
    return {"ok": True, "status": "ok"}


@app.get("/ready")
def ready():
    """Readiness: with dependency checks. When to accept traffic."""
    checks: dict[str, str] = {}
    try:
        conn = get_connection()
        try:
            conn.execute("SELECT 1").fetchone()
            checks["database"] = "ok"
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — readiness must fail closed
        # Full detail goes to JSON logs (redacted); clients get a generic fail.
        logger.error(f"readiness database check failed: {exc}")
        checks["database"] = "fail"
        return JSONResponse(
            status_code=503, content={"ready": False, "checks": checks}
        )
    return {"ready": True, "checks": checks}