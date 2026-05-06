from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Transaction
from app.schemas import ErrorResponse, PagedTransactionsResponse, TransactionOut

router = APIRouter(prefix="/v1/users/{userRef}", tags=["Transactions"])


def _normalize_from(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def _normalize_to(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.max)


def _normalize_direction_filter(direction: str | None) -> str | None:
    if direction is None:
        return None
    normalized = direction.strip().lower()
    mapping = {
        "debit": "expense",
        "credit": "income",
        "expense": "expense",
        "income": "income",
    }
    if normalized not in mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="direction must be one of income, expense, debit, credit",
        )
    return mapping[normalized]


@router.get(
    "/transactions",
    response_model=PagedTransactionsResponse,
    summary="List transactions for a user",
    description="Returns paginated transactions for a user with optional filtering by date, direction, category, and source.",
    responses={
        200: {"description": "Transactions fetched successfully."},
        400: {"model": ErrorResponse, "description": "Invalid query parameters."},
    },
)
def list_transactions(
    userRef: str = Path(..., description="Wallet user reference"),
    from_: date | datetime | None = Query(
        default=None,
        alias="from",
        description="Start date/datetime (inclusive). Example: 2026-03-01",
    ),
    to_: date | datetime | None = Query(
        default=None,
        alias="to",
        description="End date/datetime (inclusive). Example: 2026-03-31",
    ),
    direction: str | None = Query(
        default=None,
        description="Filter direction: income, expense, debit, or credit",
        examples=["expense"],
    ),
    category: str | None = Query(
        default=None,
        description="Exact category filter (case-sensitive)",
        examples=["Food"],
    ),
    source: str | None = Query(
        default=None,
        description="Source filter (normalized to lowercase)",
        examples=["wallet"],
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Page size (1-200)",
        examples=[50],
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Offset for pagination",
        examples=[0],
    ),
    db: Session = Depends(get_db),
) -> PagedTransactionsResponse:
    from_dt = _normalize_from(from_)
    to_dt = _normalize_to(to_)

    if from_dt and to_dt and from_dt > to_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from must be earlier than or equal to to",
        )

    normalized_direction = _normalize_direction_filter(direction)
    normalized_source = source.strip().lower() if source and source.strip() else None
    normalized_category = category.strip() if category and category.strip() else None

    query = db.query(Transaction).filter(Transaction.user_ref == userRef)

    if from_dt:
        query = query.filter(Transaction.occurred_at >= from_dt)
    if to_dt:
        query = query.filter(Transaction.occurred_at <= to_dt)
    if normalized_direction:
        query = query.filter(Transaction.direction == normalized_direction)
    if normalized_category:
        query = query.filter(Transaction.category == normalized_category)
    if normalized_source:
        query = query.filter(Transaction.source == normalized_source)

    total = query.count()
    items = (
        query.order_by(Transaction.occurred_at.desc(), Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return PagedTransactionsResponse(
        items=items,
        limit=limit,
        offset=offset,
        count=len(items),
        total=total,
    )


@router.get(
    "/transactions/{txId}",
    response_model=TransactionOut,
    summary="Get one transaction by ID",
    description="Returns a single transaction by internal transaction ID for the given user reference.",
    responses={
        200: {"description": "Transaction fetched successfully."},
        404: {"model": ErrorResponse, "description": "Transaction not found."},
    },
)
def get_transaction(
    userRef: str = Path(..., description="Wallet user reference"),
    txId: str = Path(..., description="Transaction ID"),
    db: Session = Depends(get_db),
) -> TransactionOut:
    item = (
        db.query(Transaction)
        .filter(Transaction.user_ref == userRef, Transaction.id == txId)
        .one_or_none()
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return item
