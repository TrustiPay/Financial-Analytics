from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Transaction, User
from app.schemas import UsersListResponse

router = APIRouter(prefix="/v1", tags=["Transactions"])


@router.get(
    "/users",
    response_model=UsersListResponse,
    summary="List known users",
    description="Returns distinct user references available in analytics data for dashboard/API consumers.",
    responses={200: {"description": "Users fetched successfully."}},
)
def list_users(db: Session = Depends(get_db)) -> UsersListResponse:
    user_refs_from_users = {row[0] for row in db.query(User.user_ref).all()}
    user_refs_from_transactions = {row[0] for row in db.query(Transaction.user_ref).distinct().all()}

    merged_refs = sorted(user_refs_from_users | user_refs_from_transactions)
    items = [{"user_ref": user_ref} for user_ref in merged_refs]
    return UsersListResponse(items=items, count=len(items))
