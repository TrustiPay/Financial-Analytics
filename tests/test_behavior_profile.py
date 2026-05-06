from datetime import date, datetime
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Transaction
from app.routers.reports import get_behavior_profile_report
from app.services.behavior_profile import build_behavior_profile, preprocess_feature_vector


def _seed_transactions(db: Session, user_ref: str, rows: list[dict]) -> None:
    for row in rows:
        occurred_at = row["occurred_at"]
        db.add(
            Transaction(
                id=str(uuid.uuid4()),
                user_ref=user_ref,
                source=row.get("source", "wallet"),
                external_tx_id=row["external_tx_id"],
                occurred_at=occurred_at,
                amount=Decimal(row["amount"]),
                direction=row["direction"],
                category=row.get("category"),
                description=row.get("description"),
                currency=row.get("currency"),
                created_at=row.get("created_at", occurred_at),
            )
        )
    db.commit()


@pytest.fixture
def db_session(tmp_path) -> Session:
    db_path = tmp_path / "behavior_profile_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_preprocess_feature_vector_imputes_none_values() -> None:
    vector = preprocess_feature_vector(
        {
            "savings_ratio": None,
            "non_essential_ratio": None,
            "spending_stability": None,
            "anomaly_rate_per_100_tx": None,
        }
    )

    assert vector.savings_ratio == 0.0
    assert vector.non_essential_ratio == 0.0
    assert vector.spending_stability == 0.5
    assert vector.anomaly_rate_per_100_tx == 0.0


def test_behavior_profile_high_savings_vector_maps_to_stable_profile() -> None:
    result = build_behavior_profile(
        user_ref="profile-user-strong",
        from_dt=datetime(2026, 3, 1, 0, 0, 0),
        to_dt=datetime(2026, 3, 31, 23, 59, 59, 999999),
        features={
            "income_total": Decimal("12000.00"),
            "expense_total": Decimal("6500.00"),
            "expense_tx_count": 8,
            "anomaly_count": 0,
            "savings_ratio": 0.45,
            "non_essential_ratio": 0.10,
            "spending_stability": 0.12,
            "anomaly_rate_per_100_tx": 0.0,
        },
    )

    assert result.profile in {"Conservative Saver", "Balanced Spender"}
    assert result.cluster_id >= 0
    assert result.distance_to_centroid >= 0


def test_behavior_profile_high_volatility_vector_maps_to_risk_profile() -> None:
    result = build_behavior_profile(
        user_ref="profile-user-risk",
        from_dt=datetime(2026, 3, 1, 0, 0, 0),
        to_dt=datetime(2026, 3, 31, 23, 59, 59, 999999),
        features={
            "income_total": Decimal("10000.00"),
            "expense_total": Decimal("13000.00"),
            "expense_tx_count": 14,
            "anomaly_count": 3,
            "savings_ratio": -0.3,
            "non_essential_ratio": 0.55,
            "spending_stability": 1.05,
            "anomaly_rate_per_100_tx": 20.0,
        },
    )

    assert result.profile == "Volatile Risk User"
    assert result.cluster_id >= 0
    assert result.distance_to_centroid >= 0


def test_behavior_profile_no_data_returns_insufficient_data() -> None:
    result = build_behavior_profile(
        user_ref="profile-user-empty",
        from_dt=datetime(2026, 3, 1, 0, 0, 0),
        to_dt=datetime(2026, 3, 31, 23, 59, 59, 999999),
        features={
            "income_total": Decimal("0"),
            "expense_total": Decimal("0"),
            "expense_tx_count": 0,
            "anomaly_count": 0,
            "savings_ratio": None,
            "non_essential_ratio": None,
            "spending_stability": None,
            "anomaly_rate_per_100_tx": 0.0,
        },
    )

    assert result.profile == "Insufficient Data"
    assert result.cluster_id == -1
    assert result.distance_to_centroid == 0.0


def test_behavior_profile_endpoint_response_shape(db_session: Session) -> None:
    user_ref = "profile-route-user"
    _seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "BPROF-1",
                "occurred_at": datetime(2026, 3, 1, 9, 0, 0),
                "amount": "10000.00",
                "direction": "income",
                "category": "Salary",
            },
            {
                "external_tx_id": "BPROF-2",
                "occurred_at": datetime(2026, 3, 3, 11, 0, 0),
                "amount": "3200.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "BPROF-3",
                "occurred_at": datetime(2026, 3, 12, 16, 30, 0),
                "amount": "2200.00",
                "direction": "expense",
                "category": "Shopping",
            },
        ],
    )

    result = get_behavior_profile_report(
        userRef=user_ref,
        month=None,
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        db=db_session,
    )

    payload = result.model_dump(by_alias=True)
    assert set(payload.keys()) == {
        "user_ref",
        "from",
        "to",
        "profile",
        "cluster_id",
        "distance_to_centroid",
        "feature_vector",
        "explanation",
    }
    assert isinstance(payload["cluster_id"], int)
    assert isinstance(payload["distance_to_centroid"], float)
    assert isinstance(payload["feature_vector"], dict)
    assert "savings_ratio" in payload["feature_vector"]
    assert payload["profile"]
