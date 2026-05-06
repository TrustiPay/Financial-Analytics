from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Transaction, User
from app.routers.users import list_users


def _seed_user(db: Session, user_ref: str) -> None:
    db.add(User(id=str(uuid.uuid4()), user_ref=user_ref, created_at=datetime(2026, 3, 1, 0, 0, 0)))
    db.commit()


def _seed_tx(db: Session, user_ref: str, external_tx_id: str) -> None:
    occurred_at = datetime(2026, 3, 2, 12, 0, 0)
    db.add(
        Transaction(
            id=str(uuid.uuid4()),
            user_ref=user_ref,
            source="wallet",
            external_tx_id=external_tx_id,
            occurred_at=occurred_at,
            amount=Decimal("100.00"),
            direction="expense",
            created_at=occurred_at,
        )
    )
    db.commit()


def test_list_users_includes_distinct_sorted_refs(tmp_path) -> None:
    db_path = tmp_path / "users_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    try:
        _seed_user(db, "demo-user-002")
        _seed_tx(db, "demo-user-001", "USERS-1")
        _seed_tx(db, "demo-user-001", "USERS-2")

        response = list_users(db=db)
        refs = [item.user_ref for item in response.items]

        assert response.count == 2
        assert refs == ["demo-user-001", "demo-user-002"]
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
