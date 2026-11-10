from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.database import engine
from app.routers import (
    account,
    auth,
    dashboard,
    onboarding,
    transaction,
)


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.connect() as connection:
        connection.execute(
            text("SELECT 1")
        )

    yield

    engine.dispose()


app = FastAPI(
    title="MaxBud API",
    version="1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(
        {
            settings.FRONTEND_ORIGIN,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        }
    ),
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
)

app.include_router(account.router)
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(transaction.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["Health"])
def health():
    with engine.connect() as connection:
        connection.execute(
            text("SELECT 1")
        )

    return {
        "status": "ok",
        "database": "connected",
    }