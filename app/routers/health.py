from fastapi import APIRouter
from pydantic import BaseModel

from app.db import check_db_connection, get_existing_tables

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
    tables: list[str]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description="Returns service health and lightweight database readiness information.",
)
def get_health() -> HealthResponse:
    db_ok = check_db_connection()
    tables = get_existing_tables() if db_ok else []

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        service="trustipay-analytics",
        version="1.0.0",
        database="ok" if db_ok else "error",
        tables=tables,
    )
