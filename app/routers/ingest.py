import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import get_db, require_ingest_key
from app.models import Transaction, User, uuid_str
from app.schemas import (
    IngestErrorItem,
    IngestTransaction,
    IngestTransactionsRequest,
    IngestTransactionsResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ingest", tags=["Ingestion"])


def normalize_direction(direction: str) -> str | None:
    normalized = direction.strip().lower()
    mapping = {
        "debit": "expense",
        "credit": "income",
        "expense": "expense",
        "income": "income",
    }
    return mapping.get(normalized)


def normalize_source(source: str | None) -> str:
    if not source or not source.strip():
        return "wallet"
    return source.strip().lower()


def _is_duplicate_error(exc: IntegrityError) -> bool:
    detail = str(exc.orig).lower() if exc.orig else str(exc).lower()
    return (
        "uq_source_external_tx_id" in detail
        or "unique constraint failed: transactions.source, transactions.external_tx_id"
        in detail
    )


def _ensure_user_exists(db: Session, user_ref: str) -> None:
    existing_user = db.execute(select(User).where(User.user_ref == user_ref)).scalar_one_or_none()
    if existing_user is None:
        db.add(User(id=uuid_str(), user_ref=user_ref))
        db.flush()


def _build_transaction(
    source: str,
    transaction: IngestTransaction,
    normalized_direction: str,
) -> Transaction:
    return Transaction(
        id=uuid_str(),
        user_ref=transaction.user_ref,
        source=source,
        external_tx_id=transaction.external_tx_id,
        occurred_at=transaction.occurred_at,
        amount=Decimal(transaction.amount),
        direction=normalized_direction,
        category=transaction.category,
        description=transaction.description,
        currency=transaction.currency,
    )


@router.post(
    "/transactions",
    response_model=IngestTransactionsResponse,
    summary="Ingest wallet transactions",
    description=(
        "Receives a batch of completed wallet transactions and stores them idempotently "
        "using the `(source, external_tx_id)` unique key."
    ),
    responses={
        200: {"description": "Batch processed with inserted/duplicate/failed counts."},
        401: {"model": ErrorResponse, "description": "Invalid or missing ingest key."},
        500: {"model": ErrorResponse, "description": "Failed to commit processed batch."},
    },
)
def ingest_transactions(
    request: IngestTransactionsRequest,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_ingest_key),
) -> IngestTransactionsResponse:
    source = normalize_source(request.source)
    received = len(request.transactions)
    inserted = 0
    duplicates = 0
    failed = 0
    errors: list[IngestErrorItem] = []

    for item in request.transactions:
        normalized_direction = normalize_direction(item.direction)
        if normalized_direction is None:
            failed += 1
            errors.append(
                IngestErrorItem(
                    external_tx_id=item.external_tx_id,
                    message="Invalid direction",
                )
            )
            continue

        try:
            with db.begin_nested():
                _ensure_user_exists(db, item.user_ref)
                db.add(_build_transaction(source, item, normalized_direction))
                db.flush()
            inserted += 1
        except IntegrityError as exc:
            if _is_duplicate_error(exc):
                duplicates += 1
            else:
                failed += 1
                errors.append(
                    IngestErrorItem(
                        external_tx_id=item.external_tx_id,
                        message="Integrity error while saving transaction",
                    )
                )
        except Exception:
            failed += 1
            errors.append(
                IngestErrorItem(
                    external_tx_id=item.external_tx_id,
                    message="Failed to ingest transaction",
                )
            )

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to commit ingested transactions",
        ) from exc

    logger.info(
        "Ingest processed source=%s received=%s inserted=%s duplicates=%s failed=%s",
        source,
        received,
        inserted,
        duplicates,
        failed,
    )

    return IngestTransactionsResponse(
        received=received,
        inserted=inserted,
        duplicates=duplicates,
        failed=failed,
        errors=errors,
    )
