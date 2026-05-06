from datetime import date, datetime
from decimal import Decimal
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Transaction
from app.routers.reports import (
    get_anomaly_impact_report,
    get_anomalies_report,
    get_categories_report,
    get_features_report,
    get_fhs_report,
    get_recommendations_report,
    get_summary_report,
    get_trends_report,
)
from app.schemas import FHSFeatureSnapshot, ReportFHSResponse
from app.services.fhs import (
    score_anomaly_rate,
    score_non_essential_ratio,
    score_savings_ratio,
    score_spending_stability,
)
from app.services.recommendations import build_recommendations


@pytest.fixture
def db_session(tmp_path) -> Session:
    db_path = tmp_path / "reports_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def seed_transactions(db: Session, user_ref: str, rows: list[dict]) -> None:
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


def make_fhs_for_tests(
    *,
    score: float = 60.0,
    interpretation: str = "Moderate",
) -> ReportFHSResponse:
    return ReportFHSResponse(
        user_ref="test-user",
        from_=datetime(2026, 3, 1, 0, 0, 0),
        to=datetime(2026, 3, 31, 23, 59, 59, 999999),
        score=score,
        max_score=100.0,
        interpretation=interpretation,
        summary="test",
        subscores=[],
        top_drivers=[],
        feature_snapshot=FHSFeatureSnapshot(
            income_total=Decimal("10000.00"),
            expense_total=Decimal("8000.00"),
            net_total=Decimal("2000.00"),
            savings_ratio=0.2,
            non_essential_ratio=0.4,
            spending_stability=0.6,
            anomaly_rate_per_100_tx=10.0,
        ),
    )


def test_summary_totals_correctness(db_session: Session) -> None:
    user_ref = "user-summary-totals"

    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "SUM-1",
                "occurred_at": datetime(2026, 3, 5, 9, 0, 0),
                "amount": "10000.00",
                "direction": "income",
            },
            {
                "external_tx_id": "SUM-2",
                "occurred_at": datetime(2026, 3, 7, 13, 30, 0),
                "amount": "2500.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "SUM-3",
                "occurred_at": datetime(2026, 3, 11, 18, 0, 0),
                "amount": "1500.00",
                "direction": "expense",
                "category": "Transport",
            },
        ],
    )

    result = get_summary_report(
        userRef=user_ref,
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        groupBy="month",
        db=db_session,
    )

    assert result.income_total == Decimal("10000.00")
    assert result.expense_total == Decimal("4000.00")
    assert result.net_total == Decimal("6000.00")
    assert len(result.series) == 1
    assert result.series[0].period == "2026-03"
    assert result.series[0].income == Decimal("10000.00")
    assert result.series[0].expense == Decimal("4000.00")
    assert result.series[0].net == Decimal("6000.00")


def test_anomaly_impact_separates_shock_from_routine_spending(db_session: Session) -> None:
    user_ref = "user-anomaly-impact"

    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "AI-INC",
                "occurred_at": datetime(2026, 4, 1, 8, 0, 0),
                "amount": "20000.00",
                "direction": "income",
                "category": "Salary",
            },
            {
                "external_tx_id": "AI-RENT",
                "occurred_at": datetime(2026, 4, 3, 9, 0, 0),
                "amount": "1000.00",
                "direction": "expense",
                "category": "Housing",
            },
            {
                "external_tx_id": "AI-UTIL",
                "occurred_at": datetime(2026, 4, 5, 10, 0, 0),
                "amount": "1000.00",
                "direction": "expense",
                "category": "Utilities",
            },
            {
                "external_tx_id": "AI-FOOD",
                "occurred_at": datetime(2026, 4, 8, 13, 0, 0),
                "amount": "1000.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "AI-TRANSPORT",
                "occurred_at": datetime(2026, 4, 11, 8, 45, 0),
                "amount": "1000.00",
                "direction": "expense",
                "category": "Transport",
            },
            {
                "external_tx_id": "AI-HEALTH",
                "occurred_at": datetime(2026, 4, 14, 12, 15, 0),
                "amount": "1000.00",
                "direction": "expense",
                "category": "Healthcare",
            },
            {
                "external_tx_id": "AI-SHOPPING",
                "occurred_at": datetime(2026, 4, 18, 18, 0, 0),
                "amount": "1000.00",
                "direction": "expense",
                "category": "Shopping",
            },
            {
                "external_tx_id": "AI-ENTERTAIN",
                "occurred_at": datetime(2026, 4, 21, 20, 0, 0),
                "amount": "1000.00",
                "direction": "expense",
                "category": "Entertainment",
            },
            {
                "external_tx_id": "AI-LUXURY",
                "occurred_at": datetime(2026, 4, 24, 23, 45, 0),
                "amount": "100000.00",
                "direction": "expense",
                "category": "Shopping",
                "description": "Unexpected luxury purchase",
            },
        ],
    )

    result = get_anomaly_impact_report(
        userRef=user_ref,
        month="2026-04",
        from_=None,
        to_=None,
        db=db_session,
    )

    assert result.income_total == Decimal("20000.00")
    assert result.expense_total == Decimal("107000.00")
    assert result.actual_net_total == Decimal("-87000.00")
    assert result.anomaly_expense_total == Decimal("100000.00")
    assert result.normal_expense_total == Decimal("7000.00")
    assert result.normal_essential_expense_total == Decimal("5000.00")
    assert result.normal_non_essential_expense_total == Decimal("2000.00")
    assert result.routine_net_total == Decimal("13000.00")
    assert result.weekly_volatility > 0
    assert result.stability_buffer == Decimal("245.00")
    assert result.monthly_recovery_capacity == Decimal("13055.00")
    assert result.estimated_recovery_months == 8
    assert result.recommended_non_essential_cut == Decimal("300.00")
    assert result.anomaly_count == 1
    assert result.anomaly_transactions[0].external_tx_id == "AI-LUXURY"


def test_anomaly_impact_no_anomaly_keeps_normal_expenses_equal_total(db_session: Session) -> None:
    user_ref = "user-no-anomaly-impact"

    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "NAI-INC",
                "occurred_at": datetime(2026, 4, 1, 8, 0, 0),
                "amount": "15000.00",
                "direction": "income",
            },
            {
                "external_tx_id": "NAI-FOOD",
                "occurred_at": datetime(2026, 4, 8, 13, 0, 0),
                "amount": "3000.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "NAI-SHOPPING",
                "occurred_at": datetime(2026, 4, 18, 18, 0, 0),
                "amount": "2000.00",
                "direction": "expense",
                "category": "Shopping",
            },
        ],
    )

    result = get_anomaly_impact_report(
        userRef=user_ref,
        month="2026-04",
        from_=None,
        to_=None,
        db=db_session,
    )

    assert result.anomaly_expense_total == Decimal("0")
    assert result.normal_expense_total == Decimal("5000.00")
    assert result.routine_net_total == Decimal("10000.00")
    assert result.weekly_volatility == 0.0
    assert result.stability_buffer == Decimal("0.00")
    assert result.monthly_recovery_capacity == Decimal("10000.00")
    assert result.estimated_recovery_months == 0
    assert result.anomaly_transactions == []


def test_summary_groupby_month_creates_two_buckets(db_session: Session) -> None:
    user_ref = "user-groupby-month"

    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "GB-1",
                "occurred_at": datetime(2026, 1, 10, 10, 0, 0),
                "amount": "5000.00",
                "direction": "income",
            },
            {
                "external_tx_id": "GB-2",
                "occurred_at": datetime(2026, 1, 12, 14, 0, 0),
                "amount": "1000.00",
                "direction": "expense",
            },
            {
                "external_tx_id": "GB-3",
                "occurred_at": datetime(2026, 2, 8, 9, 15, 0),
                "amount": "3000.00",
                "direction": "income",
            },
            {
                "external_tx_id": "GB-4",
                "occurred_at": datetime(2026, 2, 15, 11, 45, 0),
                "amount": "500.00",
                "direction": "expense",
            },
        ],
    )

    result = get_summary_report(
        userRef=user_ref,
        from_=date(2026, 1, 1),
        to_=date(2026, 2, 28),
        groupBy="month",
        db=db_session,
    )

    assert len(result.series) == 2

    jan_bucket = result.series[0]
    feb_bucket = result.series[1]

    assert jan_bucket.period == "2026-01"
    assert jan_bucket.income == Decimal("5000.00")
    assert jan_bucket.expense == Decimal("1000.00")
    assert jan_bucket.net == Decimal("4000.00")

    assert feb_bucket.period == "2026-02"
    assert feb_bucket.income == Decimal("3000.00")
    assert feb_bucket.expense == Decimal("500.00")
    assert feb_bucket.net == Decimal("2500.00")


def test_categories_totals_counts_and_sorting(db_session: Session) -> None:
    user_ref = "user-categories"

    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "CAT-1",
                "occurred_at": datetime(2026, 3, 4, 8, 0, 0),
                "amount": "2000.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "CAT-2",
                "occurred_at": datetime(2026, 3, 5, 9, 0, 0),
                "amount": "1000.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "CAT-3",
                "occurred_at": datetime(2026, 3, 6, 10, 0, 0),
                "amount": "500.00",
                "direction": "expense",
                "category": "Transport",
            },
            {
                "external_tx_id": "CAT-4",
                "occurred_at": datetime(2026, 3, 7, 11, 0, 0),
                "amount": "12000.00",
                "direction": "income",
                "category": "Salary",
            },
        ],
    )

    result = get_categories_report(
        userRef=user_ref,
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        db=db_session,
    )

    assert result.expense_total == Decimal("3500.00")
    assert len(result.items) == 2

    first = result.items[0]
    second = result.items[1]

    assert first.category == "Food"
    assert first.expense_total == Decimal("3000.00")
    assert first.transaction_count == 2

    assert second.category == "Transport"
    assert second.expense_total == Decimal("500.00")
    assert second.transaction_count == 1


def test_trends_report_detects_material_drift(db_session: Session) -> None:
    user_ref = "user-trends-drift"

    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "TR-BASE-1",
                "occurred_at": datetime(2026, 3, 1, 9, 0, 0),
                "amount": "10000.00",
                "direction": "income",
            },
            {
                "external_tx_id": "TR-BASE-2",
                "occurred_at": datetime(2026, 3, 2, 12, 0, 0),
                "amount": "1500.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "TR-BASE-3",
                "occurred_at": datetime(2026, 3, 4, 18, 0, 0),
                "amount": "1500.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "TR-CUR-1",
                "occurred_at": datetime(2026, 3, 8, 9, 0, 0),
                "amount": "10000.00",
                "direction": "income",
            },
            {
                "external_tx_id": "TR-CUR-2",
                "occurred_at": datetime(2026, 3, 9, 12, 0, 0),
                "amount": "2200.00",
                "direction": "expense",
                "category": "Shopping",
            },
            {
                "external_tx_id": "TR-CUR-3",
                "occurred_at": datetime(2026, 3, 10, 20, 0, 0),
                "amount": "1800.00",
                "direction": "expense",
                "category": "Entertainment",
            },
            {
                "external_tx_id": "TR-CUR-4",
                "occurred_at": datetime(2026, 3, 12, 11, 0, 0),
                "amount": "1200.00",
                "direction": "expense",
                "category": "Food",
            },
        ],
    )

    result = get_trends_report(
        userRef=user_ref,
        from_=date(2026, 3, 8),
        to_=date(2026, 3, 14),
        groupBy="week",
        db=db_session,
    )

    assert result.baseline_available is True
    assert result.drift_detected is True
    assert result.group_by == "week"
    assert len(result.series) == 1
    assert result.current_snapshot.expense_total == Decimal("5200.00")
    assert result.baseline_snapshot is not None
    assert result.baseline_snapshot.expense_total == Decimal("3000.00")

    metrics = {item.metric for item in result.drift_items}
    assert "expense_total" in metrics
    assert "non_essential_ratio" in metrics


def test_trends_report_handles_missing_baseline_history(db_session: Session) -> None:
    user_ref = "user-trends-no-baseline"

    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "TR-NB-1",
                "occurred_at": datetime(2026, 4, 8, 10, 0, 0),
                "amount": "5000.00",
                "direction": "income",
            },
            {
                "external_tx_id": "TR-NB-2",
                "occurred_at": datetime(2026, 4, 9, 13, 0, 0),
                "amount": "1200.00",
                "direction": "expense",
                "category": "Food",
            },
        ],
    )

    result = get_trends_report(
        userRef=user_ref,
        from_=date(2026, 4, 8),
        to_=date(2026, 4, 14),
        groupBy="week",
        db=db_session,
    )

    assert result.baseline_available is False
    assert result.drift_detected is False
    assert result.baseline_snapshot is None
    assert result.drift_items == []
    assert "not enough prior history" in result.summary.lower()


def test_to_date_includes_end_of_day_transactions(db_session: Session) -> None:
    user_ref = "user-date-boundary"

    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "BOUND-1",
                "occurred_at": datetime(2026, 3, 31, 23, 59, 59),
                "amount": "100.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "BOUND-2",
                "occurred_at": datetime(2026, 4, 1, 0, 0, 0),
                "amount": "200.00",
                "direction": "expense",
                "category": "Food",
            },
        ],
    )

    result = get_summary_report(
        userRef=user_ref,
        from_=date(2026, 3, 31),
        to_=date(2026, 3, 31),
        groupBy="day",
        db=db_session,
    )

    assert result.expense_total == Decimal("100.00")
    assert len(result.series) == 1
    assert result.series[0].period == "2026-03-31"
    assert result.series[0].expense == Decimal("100.00")


def test_transaction_outlier_detection(db_session: Session) -> None:
    user_ref = "user-anomaly-outlier"
    rows = []
    for idx in range(7):
        rows.append(
            {
                "external_tx_id": f"OUT-{idx}",
                "occurred_at": datetime(2026, 3, idx + 1, 12, 0, 0),
                "amount": "100.00",
                "direction": "expense",
                "category": "Food",
            }
        )
    rows.append(
        {
            "external_tx_id": "OUT-BIG",
            "occurred_at": datetime(2026, 3, 20, 12, 0, 0),
            "amount": "2000.00",
            "direction": "expense",
            "category": "Shopping",
            "description": "High-value purchase",
        }
    )
    seed_transactions(db_session, user_ref, rows)

    result = get_anomalies_report(
        userRef=user_ref,
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        db=db_session,
    )

    tx_outliers = [item for item in result.items if item.type == "transaction_outlier"]
    assert len(tx_outliers) == 1
    anomaly = tx_outliers[0]
    assert anomaly.external_tx_id == "OUT-BIG"
    assert anomaly.category == "Shopping"
    assert anomaly.score >= 2.5
    assert "unusually high" in anomaly.reason


def test_weekly_spike_detection(db_session: Session) -> None:
    user_ref = "user-anomaly-weekly"
    rows = []

    # Baseline: one small expense in each week.
    baseline_dates = [
        datetime(2026, 1, 5, 10, 0, 0),   # 2026-W02
        datetime(2026, 1, 12, 10, 0, 0),  # 2026-W03
        datetime(2026, 1, 19, 10, 0, 0),  # 2026-W04
        datetime(2026, 1, 26, 10, 0, 0),  # 2026-W05
        datetime(2026, 2, 2, 10, 0, 0),   # 2026-W06
        datetime(2026, 2, 9, 10, 0, 0),   # 2026-W07
        datetime(2026, 2, 16, 10, 0, 0),  # 2026-W08
    ]
    for idx, dt in enumerate(baseline_dates):
        rows.append(
            {
                "external_tx_id": f"WK-BASE-{idx}",
                "occurred_at": dt,
                "amount": "100.00",
                "direction": "expense",
                "category": "Food",
            }
        )

    # Spike week: 2026-W09
    rows.append(
        {
            "external_tx_id": "WK-SPIKE",
            "occurred_at": datetime(2026, 2, 23, 10, 0, 0),
            "amount": "2000.00",
            "direction": "expense",
            "category": "Shopping",
        }
    )
    seed_transactions(db_session, user_ref, rows)

    result = get_anomalies_report(
        userRef=user_ref,
        from_=date(2026, 1, 1),
        to_=date(2026, 2, 28),
        db=db_session,
    )

    weekly_spikes = [item for item in result.items if item.type == "weekly_spike"]
    assert len(weekly_spikes) == 1
    spike = weekly_spikes[0]
    assert spike.period == "2026-W09"
    assert spike.amount == Decimal("2000.00")
    assert spike.score >= 2.5


def test_anomalies_std_zero_returns_empty(db_session: Session) -> None:
    user_ref = "user-anomaly-std-zero"
    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "ZERO-1",
                "occurred_at": datetime(2026, 3, 1, 10, 0, 0),
                "amount": "100.00",
                "direction": "expense",
            },
            {
                "external_tx_id": "ZERO-2",
                "occurred_at": datetime(2026, 3, 2, 10, 0, 0),
                "amount": "100.00",
                "direction": "expense",
            },
            {
                "external_tx_id": "ZERO-3",
                "occurred_at": datetime(2026, 3, 3, 10, 0, 0),
                "amount": "100.00",
                "direction": "expense",
            },
        ],
    )

    result = get_anomalies_report(
        userRef=user_ref,
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        db=db_session,
    )

    assert result.anomaly_count == 0
    assert result.items == []


def test_anomalies_endpoint_response_shape(db_session: Session) -> None:
    user_ref = "user-anomaly-shape"
    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "SHAPE-1",
                "occurred_at": datetime(2026, 3, 1, 10, 0, 0),
                "amount": "100.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "SHAPE-2",
                "occurred_at": datetime(2026, 3, 2, 10, 0, 0),
                "amount": "100.00",
                "direction": "expense",
                "category": "Food",
            },
        ],
    )

    result = get_anomalies_report(
        userRef=user_ref,
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        db=db_session,
    )
    payload = result.model_dump(by_alias=True)

    assert set(payload.keys()) == {"user_ref", "from", "to", "anomaly_count", "items"}
    assert isinstance(payload["items"], list)


def test_features_savings_ratio(db_session: Session) -> None:
    user_ref = "user-features-savings"
    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "FS-1",
                "occurred_at": datetime(2026, 3, 1, 10, 0, 0),
                "amount": "10000.00",
                "direction": "income",
            },
            {
                "external_tx_id": "FS-2",
                "occurred_at": datetime(2026, 3, 2, 10, 0, 0),
                "amount": "4000.00",
                "direction": "expense",
                "category": "Food",
            },
        ],
    )

    result = get_features_report(
        userRef=user_ref,
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        db=db_session,
    )

    assert result.income_total == Decimal("10000.00")
    assert result.expense_total == Decimal("4000.00")
    assert result.net_total == Decimal("6000.00")
    assert result.savings_ratio == pytest.approx(0.6)


def test_features_non_essential_ratio(db_session: Session) -> None:
    user_ref = "user-features-non-essential"
    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "FNE-1",
                "occurred_at": datetime(2026, 3, 1, 10, 0, 0),
                "amount": "100.00",
                "direction": "expense",
                "category": "Food",
            },
            {
                "external_tx_id": "FNE-2",
                "occurred_at": datetime(2026, 3, 2, 10, 0, 0),
                "amount": "300.00",
                "direction": "expense",
                "category": "Shopping",
            },
            {
                "external_tx_id": "FNE-3",
                "occurred_at": datetime(2026, 3, 3, 10, 0, 0),
                "amount": "100.00",
                "direction": "expense",
                "category": "Entertainment",
            },
        ],
    )

    result = get_features_report(
        userRef=user_ref,
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        db=db_session,
    )

    assert result.expense_total == Decimal("500.00")
    assert result.non_essential_expense_total == Decimal("400.00")
    assert result.essential_expense_total == Decimal("100.00")
    assert result.non_essential_ratio == pytest.approx(0.8)


def test_features_spending_stability_computed(db_session: Session) -> None:
    user_ref = "user-features-stability"
    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "FST-1",
                "occurred_at": datetime(2026, 1, 5, 10, 0, 0),  # W02
                "amount": "100.00",
                "direction": "expense",
            },
            {
                "external_tx_id": "FST-2",
                "occurred_at": datetime(2026, 1, 12, 10, 0, 0),  # W03
                "amount": "300.00",
                "direction": "expense",
            },
            {
                "external_tx_id": "FST-3",
                "occurred_at": datetime(2026, 1, 19, 10, 0, 0),  # W04
                "amount": "500.00",
                "direction": "expense",
            },
        ],
    )

    result = get_features_report(
        userRef=user_ref,
        from_=date(2026, 1, 1),
        to_=date(2026, 1, 31),
        db=db_session,
    )

    assert result.weeks_count == 3
    assert result.weekly_expense_mean is not None
    assert result.weekly_expense_std is not None
    assert result.spending_stability is not None
    assert result.spending_stability == pytest.approx(0.5443310539)
    assert result.spending_frequency == pytest.approx(1.0)


def test_features_empty_range(db_session: Session) -> None:
    result = get_features_report(
        userRef="user-features-empty",
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        db=db_session,
    )

    assert result.income_total == Decimal("0")
    assert result.expense_total == Decimal("0")
    assert result.net_total == Decimal("0")
    assert result.savings_ratio is None
    assert result.non_essential_ratio is None
    assert result.weekly_expense_mean is None
    assert result.weekly_expense_std is None
    assert result.spending_stability is None
    assert result.spending_frequency == 0
    assert result.anomaly_count == 0
    assert result.anomaly_rate_per_100_tx == 0


def test_features_month_parsing_and_boundaries(db_session: Session) -> None:
    user_ref = "user-features-month"
    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "FM-1",
                "occurred_at": datetime(2026, 3, 15, 10, 0, 0),
                "amount": "500.00",
                "direction": "expense",
            },
            {
                "external_tx_id": "FM-2",
                "occurred_at": datetime(2026, 4, 15, 10, 0, 0),
                "amount": "700.00",
                "direction": "expense",
            },
        ],
    )

    with pytest.raises(HTTPException) as exc:
        get_features_report(
            userRef=user_ref,
            month="2026-13",
            db=db_session,
        )
    assert exc.value.status_code == 400

    valid = get_features_report(
        userRef=user_ref,
        month="2026-03",
        from_=date(2026, 4, 1),
        to_=date(2026, 4, 30),
        db=db_session,
    )
    assert valid.from_ == datetime(2026, 3, 1, 0, 0, 0)
    assert valid.to == datetime(2026, 3, 31, 23, 59, 59, 999999)
    assert valid.expense_total == Decimal("500.00")


def test_fhs_scoring_functions() -> None:
    assert score_savings_ratio(0.45)[0] == 35.0
    assert score_savings_ratio(-0.30)[0] == 0.0
    assert score_non_essential_ratio(0.08)[0] == 25.0
    assert score_spending_stability(0.05)[0] == 25.0
    assert score_anomaly_rate(0)[0] == 15.0


def test_fhs_endpoint_shape_and_range(db_session: Session) -> None:
    user_ref = "user-fhs-shape"
    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "FHS-1",
                "occurred_at": datetime(2026, 3, 1, 10, 0, 0),
                "amount": "10000.00",
                "direction": "income",
            },
            {
                "external_tx_id": "FHS-2",
                "occurred_at": datetime(2026, 3, 2, 10, 0, 0),
                "amount": "8500.00",
                "direction": "expense",
                "category": "Shopping",
            },
            {
                "external_tx_id": "FHS-3",
                "occurred_at": datetime(2026, 3, 10, 10, 0, 0),
                "amount": "1500.00",
                "direction": "expense",
                "category": "Food",
            },
        ],
    )

    result = get_fhs_report(
        userRef=user_ref,
        month=None,
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        db=db_session,
    )

    assert 0 <= result.score <= 100
    assert result.max_score == 100.0
    assert isinstance(result.interpretation, str)
    assert isinstance(result.summary, str)
    assert len(result.subscores) == 4
    assert len(result.top_drivers) >= 1


def test_fhs_no_data_response(db_session: Session) -> None:
    result = get_fhs_report(
        userRef="user-fhs-empty",
        month=None,
        from_=date(2026, 3, 1),
        to_=date(2026, 3, 31),
        db=db_session,
    )

    assert result.score == 0
    assert result.interpretation == "Insufficient Data"
    assert "Insufficient transaction data" in result.summary


def test_recommendations_low_savings_rule() -> None:
    features = {
        "savings_ratio": 0.05,
        "non_essential_ratio": 0.20,
        "spending_stability": 0.25,
        "anomaly_count": 0,
        "anomaly_rate_per_100_tx": 0.0,
        "non_essential_expense_total": Decimal("200.00"),
        "income_total": Decimal("10000.00"),
        "expense_total": Decimal("9500.00"),
    }
    fhs = make_fhs_for_tests(score=52.0, interpretation="Moderate")
    items = build_recommendations(features=features, fhs_result=fhs)

    assert any(item.component == "savings_ratio" for item in items)
    savings_item = next(item for item in items if item.component == "savings_ratio")
    assert savings_item.title == "Improve monthly savings"


def test_recommendations_high_non_essential_rule() -> None:
    features = {
        "savings_ratio": 0.20,
        "non_essential_ratio": 0.55,
        "spending_stability": 0.25,
        "anomaly_count": 0,
        "anomaly_rate_per_100_tx": 0.0,
        "non_essential_expense_total": Decimal("5000.00"),
        "income_total": Decimal("10000.00"),
        "expense_total": Decimal("9000.00"),
    }
    fhs = make_fhs_for_tests(score=49.0, interpretation="At Risk")
    items = build_recommendations(features=features, fhs_result=fhs)

    assert any(item.component == "non_essential_ratio" for item in items)
    target = next(item for item in items if item.component == "non_essential_ratio")
    assert target.priority in {"high", "medium"}
    assert "discretionary" in target.reason.lower()


def test_recommendations_anomaly_rule() -> None:
    features = {
        "savings_ratio": 0.20,
        "non_essential_ratio": 0.10,
        "spending_stability": 0.20,
        "anomaly_count": 2,
        "anomaly_rate_per_100_tx": 12.0,
        "non_essential_expense_total": Decimal("200.00"),
        "income_total": Decimal("10000.00"),
        "expense_total": Decimal("7000.00"),
    }
    fhs = make_fhs_for_tests(score=58.0, interpretation="Moderate")
    items = build_recommendations(features=features, fhs_result=fhs)

    assert any(item.component == "anomaly_risk" for item in items)
    anomaly_item = next(item for item in items if item.component == "anomaly_risk")
    assert "unusual" in anomaly_item.title.lower() or "anomal" in anomaly_item.reason.lower()


def test_recommendations_fallback_rule() -> None:
    features = {
        "savings_ratio": 0.45,
        "non_essential_ratio": 0.10,
        "spending_stability": 0.10,
        "anomaly_count": 0,
        "anomaly_rate_per_100_tx": 0.0,
        "non_essential_expense_total": Decimal("100.00"),
        "income_total": Decimal("10000.00"),
        "expense_total": Decimal("5500.00"),
    }
    fhs = make_fhs_for_tests(score=86.0, interpretation="Excellent")
    items = build_recommendations(features=features, fhs_result=fhs)

    assert len(items) >= 1
    assert any(item.title == "Maintain current discipline" for item in items)


def test_recommendations_endpoint_integration(db_session: Session) -> None:
    user_ref = "user-recommendations-endpoint"
    seed_transactions(
        db_session,
        user_ref,
        [
            {
                "external_tx_id": "REC-1",
                "occurred_at": datetime(2026, 3, 1, 10, 0, 0),
                "amount": "10000.00",
                "direction": "income",
            },
            {
                "external_tx_id": "REC-2",
                "occurred_at": datetime(2026, 3, 2, 10, 0, 0),
                "amount": "7000.00",
                "direction": "expense",
                "category": "Shopping",
            },
            {
                "external_tx_id": "REC-3",
                "occurred_at": datetime(2026, 3, 10, 10, 0, 0),
                "amount": "2600.00",
                "direction": "expense",
                "category": "Entertainment",
            },
            {
                "external_tx_id": "REC-4",
                "occurred_at": datetime(2026, 3, 20, 10, 0, 0),
                "amount": "1500.00",
                "direction": "expense",
                "category": "Food",
            },
        ],
    )

    result = get_recommendations_report(
        userRef=user_ref,
        month="2026-03",
        db=db_session,
    )

    assert isinstance(result.fhs_score, float)
    assert isinstance(result.interpretation, str)
    assert len(result.items) >= 1
    ranks = [item.rank for item in result.items]
    assert ranks == sorted(ranks)
    assert ranks[0] == 1
