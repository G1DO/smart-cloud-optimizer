from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_api.routers.costs import router as costs_router
from backend_api.routers.dashboard import router as dashboard_router
from backend_api.routers.forecast import router as forecast_router
from backend_api.routers.recommendations import router as recommendations_router
from backend_api.routers.auth import router as auth_router
from backend_api.routers.settings import router as settings_router
from backend_api.routers.on_boarding import router as onboarding_router
from backend_api.routers.connections import router as connections_router

from storage.db import get_connection, ensure_schema, ensure_user


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
    return {"ok": True}