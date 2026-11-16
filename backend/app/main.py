from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.database import engine
from app.core.rate_limit import RequestLimits
from app.routers import (
    account,
    auth,
    dashboard,
    onboarding,
    transaction,
)
from app.routers import budgets
from app.routers import family, goals, reminders, settings as account_settings, admin, ai, notifications, subscriptions, household


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
    docs_url=None if settings.ENVIRONMENT in {"beta", "production"} else "/docs",
    redoc_url=None if settings.ENVIRONMENT in {"beta", "production"} else "/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestLimits)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN] if settings.ENVIRONMENT in {"beta", "production"} else list({settings.FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"}),
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
        "Idempotency-Key",
    ],
)

app.include_router(account.router)
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(transaction.router)
app.include_router(dashboard.router)
app.include_router(budgets.router)
app.include_router(family.router)
app.include_router(goals.router)
app.include_router(reminders.router)
app.include_router(account_settings.router)
app.include_router(admin.router)
app.include_router(ai.router)
app.include_router(notifications.router)
app.include_router(subscriptions.router)
app.include_router(household.router)


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
