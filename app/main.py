from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.db import DB_URL, init_db
from app.routers import health, ingest, reports, transactions, users

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

logger = logging.getLogger(__name__)

OPENAPI_TAGS = [
    {"name": "Health", "description": "Service health and readiness checks."},
    {"name": "Ingestion", "description": "Wallet transaction ingestion endpoints."},
    {"name": "Transactions", "description": "Read-only transaction lookup APIs."},
    {"name": "Reports", "description": "Analytics, scoring, and recommendations reports."},
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Initializing database with DB_URL=%s", DB_URL)
    init_db()
    logger.info("DB tables ensured/created")
    yield


app = FastAPI(
    title="TrustiPay Analytics & Scoring Service",
    version="1.0.0",
    description=(
        "Ingests completed wallet transactions into a derived analytics store and "
        "exposes deterministic reporting APIs for summaries, anomaly detection, "
        "behavior features, financial health scoring, behavior profiling, and recommendations."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "TrustiPay Analytics", "email": "analytics@trustipay.local"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(users.router)
app.include_router(transactions.router)
app.include_router(reports.router)


@app.get("/", tags=["Meta"])
def root() -> dict[str, str]:
    return {"message": "TrustiPay Analytics & Scoring Service is running."}
