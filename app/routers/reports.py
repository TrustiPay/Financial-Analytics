import calendar
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Transaction
from app.schemas import (
    AnomalyItem,
    AnomalyPredictRequest,
    BatchAnomalyPredictRequest,
    BatchAnomalyPredictResponse,
    BatchTransactionPrediction,
    CategoryTotal,
    ErrorResponse,
    PredictionXAIFactor,
    ReportAnomalyImpactResponse,
    RecommendationItem,
    ReportAnomalyPredictResponse,
    ReportAnomaliesResponse,
    ReportBehaviorProfileResponse,
    ReportCategoriesResponse,
    ReportFeaturesResponse,
    ReportFHSResponse,
    ReportRecommendationsResponse,
    ReportSummaryResponse,
    ReportTrendsResponse,
    SummaryPoint,
)
from app.services.anomalies import detect_anomalies, predict_transaction_risks
from app.services.anomaly_impact import build_anomaly_impact
from app.services.behavior_profile import build_behavior_profile
from app.services.features import compute_features
from app.services.fhs import build_fhs
from app.services.recommendations import build_recommendations
from app.services.trends import build_trend_report
from app.services.reports_summary import (
    compute_category_breakdown,
    compute_summary,
    fetch_transactions,
)

router = APIRouter(prefix="/v1/users/{userRef}/reports", tags=["Reports"])
logger = logging.getLogger(__name__)

MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")
GROUP_BY_VALUES = {"day", "week", "month"}


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


def _resolve_window(
    from_value: date | datetime | None,
    to_value: date | datetime | None,
) -> tuple[datetime, datetime]:
    # Keep window bounds naive UTC to match existing DB/query expectations.
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    to_dt = _normalize_to(to_value) if to_value is not None else now_utc
    from_dt = _normalize_from(from_value) if from_value is not None else to_dt - timedelta(days=30)

    if from_dt > to_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from must be earlier than or equal to to",
        )

    return from_dt, to_dt


def _resolve_month_window(month_value: str) -> tuple[datetime, datetime]:
    if not MONTH_PATTERN.fullmatch(month_value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="month must be in YYYY-MM format",
        )
    try:
        year = int(month_value[:4])
        month = int(month_value[5:7])
        month_last_day = calendar.monthrange(year, month)[1]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="month must be in YYYY-MM format",
        )

    from_dt = datetime(year, month, 1, 0, 0, 0)
    to_dt = datetime(year, month, month_last_day, 23, 59, 59, 999999)
    return from_dt, to_dt


def _normalize_group_by(group_by: str) -> str:
    normalized = group_by.strip().lower()
    if normalized not in GROUP_BY_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="groupBy must be one of: day, week, month",
        )
    return normalized


def _resolve_previous_window(
    from_dt: datetime,
    to_dt: datetime,
) -> tuple[datetime, datetime]:
    duration = to_dt - from_dt
    baseline_to = from_dt - timedelta(microseconds=1)
    baseline_from = baseline_to - duration
    return baseline_from, baseline_to


def _resolve_previous_month_window(month_value: str) -> tuple[datetime, datetime]:
    year = int(month_value[:4])
    month = int(month_value[5:7])
    previous_month = month - 1
    previous_year = year
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1

    month_last_day = calendar.monthrange(previous_year, previous_month)[1]
    from_dt = datetime(previous_year, previous_month, 1, 0, 0, 0)
    to_dt = datetime(previous_year, previous_month, month_last_day, 23, 59, 59, 999999)
    return from_dt, to_dt


@router.get(
    "/summary",
    response_model=ReportSummaryResponse,
    summary="Summary report for income, expense, and net",
    description=(
        "Returns aggregated income, expense, and net values for the selected period, "
        "with grouped time-series buckets by day, week, or month."
    ),
    responses={
        200: {"description": "Summary report generated successfully."},
        400: {"model": ErrorResponse, "description": "Invalid date range or groupBy value."},
    },
)
def get_summary_report(
    userRef: str = Path(..., description="Wallet user reference"),
    from_: date | datetime | None = Query(
        default=None,
        alias="from",
        description="Start date/datetime (inclusive). Example: 2026-03-01",
        examples=["2026-03-01"],
    ),
    to_: date | datetime | None = Query(
        default=None,
        alias="to",
        description="End date/datetime (inclusive). Example: 2026-03-31",
        examples=["2026-03-31"],
    ),
    groupBy: str = Query(
        default="month",
        description="Series grouping: day, week, or month",
        examples=["month"],
    ),
    db: Session = Depends(get_db),
) -> ReportSummaryResponse:
    from_dt, to_dt = _resolve_window(from_, to_)
    group_by = _normalize_group_by(groupBy)
    logger.info("Summary report user_ref=%s from=%s to=%s group_by=%s", userRef, from_dt, to_dt, group_by)
    transactions = fetch_transactions(db, userRef, from_dt, to_dt)
    income_total, expense_total, series_data = compute_summary(transactions, group_by)

    series = [SummaryPoint(**item) for item in series_data]

    return ReportSummaryResponse(
        user_ref=userRef,
        from_=from_dt,
        to=to_dt,
        group_by=group_by,
        income_total=income_total,
        expense_total=expense_total,
        net_total=income_total - expense_total,
        series=series,
    )


@router.get(
    "/categories",
    response_model=ReportCategoriesResponse,
    summary="Expense category totals for a period",
    description="Returns expense totals and transaction counts grouped by category for the selected period.",
    responses={
        200: {"description": "Category report generated successfully."},
        400: {"model": ErrorResponse, "description": "Invalid date range."},
    },
)
def get_categories_report(
    userRef: str = Path(..., description="Wallet user reference"),
    from_: date | datetime | None = Query(
        default=None,
        alias="from",
        description="Start date/datetime (inclusive). Example: 2026-03-01",
        examples=["2026-03-01"],
    ),
    to_: date | datetime | None = Query(
        default=None,
        alias="to",
        description="End date/datetime (inclusive). Example: 2026-03-31",
        examples=["2026-03-31"],
    ),
    db: Session = Depends(get_db),
) -> ReportCategoriesResponse:
    from_dt, to_dt = _resolve_window(from_, to_)
    logger.info("Categories report user_ref=%s from=%s to=%s", userRef, from_dt, to_dt)
    transactions = fetch_transactions(db, userRef, from_dt, to_dt)
    items_data, expense_total = compute_category_breakdown(transactions)

    items = [CategoryTotal(**item) for item in items_data]

    return ReportCategoriesResponse(
        user_ref=userRef,
        from_=from_dt,
        to=to_dt,
        items=items,
        expense_total=expense_total,
    )


@router.get(
    "/anomalies",
    response_model=ReportAnomaliesResponse,
    summary="Detect unusual spending anomalies",
    description=(
        "Detects unusual spending using deterministic z-score signals and model-based risk scoring "
        "when a trained anomaly artifact is available."
    ),
    responses={
        200: {"description": "Anomalies report generated successfully."},
        400: {"model": ErrorResponse, "description": "Invalid date range."},
    },
)
def get_anomalies_report(
    userRef: str = Path(..., description="Wallet user reference"),
    from_: date | datetime | None = Query(
        default=None,
        alias="from",
        description="Start date/datetime (inclusive). Example: 2026-03-01",
        examples=["2026-03-01"],
    ),
    to_: date | datetime | None = Query(
        default=None,
        alias="to",
        description="End date/datetime (inclusive). Example: 2026-03-31",
        examples=["2026-03-31"],
    ),
    db: Session = Depends(get_db),
) -> ReportAnomaliesResponse:
    from_dt, to_dt = _resolve_window(from_, to_)
    logger.info("Anomalies report user_ref=%s from=%s to=%s", userRef, from_dt, to_dt)
    transactions = fetch_transactions(db, userRef, from_dt, to_dt)
    anomaly_items = [AnomalyItem(**item) for item in detect_anomalies(transactions)]

    return ReportAnomaliesResponse(
        user_ref=userRef,
        from_=from_dt,
        to=to_dt,
        anomaly_count=len(anomaly_items),
        items=anomaly_items,
    )


@router.get(
    "/anomaly-impact",
    response_model=ReportAnomalyImpactResponse,
    summary="Separate anomaly impact from routine spending",
    description=(
        "Returns an advisory managed view that isolates transaction-level anomaly expenses "
        "from routine expenses. Actual totals remain unchanged and wallet transactions are never mutated."
    ),
    responses={
        200: {"description": "Anomaly impact report generated successfully."},
        400: {"model": ErrorResponse, "description": "Invalid month format or date range."},
    },
)
def get_anomaly_impact_report(
    userRef: str = Path(..., description="Wallet user reference"),
    month: str | None = Query(
        default=None,
        description="Optional month in YYYY-MM format. If provided, month takes precedence over from/to.",
        examples=["2026-04"],
    ),
    from_: date | datetime | None = Query(
        default=None,
        alias="from",
        description="Start date/datetime (inclusive). Example: 2026-04-01",
        examples=["2026-04-01"],
    ),
    to_: date | datetime | None = Query(
        default=None,
        alias="to",
        description="End date/datetime (inclusive). Example: 2026-04-30",
        examples=["2026-04-30"],
    ),
    db: Session = Depends(get_db),
) -> ReportAnomalyImpactResponse:
    month_value = month.strip() if isinstance(month, str) else None
    if month_value:
        from_dt, to_dt = _resolve_month_window(month_value)
    else:
        from_dt, to_dt = _resolve_window(from_, to_)

    logger.info("Anomaly impact report user_ref=%s from=%s to=%s", userRef, from_dt, to_dt)
    transactions = fetch_transactions(db, userRef, from_dt, to_dt)
    impact = build_anomaly_impact(transactions)

    return ReportAnomalyImpactResponse(
        user_ref=userRef,
        from_=from_dt,
        to=to_dt,
        **impact,
    )


@router.get(
    "/features",
    response_model=ReportFeaturesResponse,
    summary="Behavioral features for scoring",
    description=(
        "Computes behavior metrics used by scoring, including savings, non-essential share, "
        "weekly stability, frequency, and anomaly statistics."
    ),
    responses={
        200: {"description": "Features report generated successfully."},
        400: {"model": ErrorResponse, "description": "Invalid month format or date range."},
    },
)
def get_features_report(
    userRef: str = Path(..., description="Wallet user reference"),
    month: str | None = Query(
        default=None,
        description="Optional month in YYYY-MM format. If provided, month takes precedence over from/to.",
        examples=["2026-03"],
    ),
    from_: date | datetime | None = Query(
        default=None,
        alias="from",
        description="Start date/datetime (inclusive). Example: 2026-03-01",
        examples=["2026-03-01"],
    ),
    to_: date | datetime | None = Query(
        default=None,
        alias="to",
        description="End date/datetime (inclusive). Example: 2026-03-31",
        examples=["2026-03-31"],
    ),
    db: Session = Depends(get_db),
) -> ReportFeaturesResponse:
    month_value = month.strip() if isinstance(month, str) else None
    if month_value:
        from_dt, to_dt = _resolve_month_window(month_value)
    else:
        from_dt, to_dt = _resolve_window(from_, to_)

    logger.info("Features report user_ref=%s from=%s to=%s", userRef, from_dt, to_dt)
    transactions = fetch_transactions(db, userRef, from_dt, to_dt)
    feature_values = compute_features(transactions)

    return ReportFeaturesResponse(
        user_ref=userRef,
        from_=from_dt,
        to=to_dt,
        **feature_values,
    )


@router.get(
    "/trends",
    response_model=ReportTrendsResponse,
    summary="Trend and drift detection for spending behavior",
    description=(
        "Builds a trend series for the selected window and compares it against a prior baseline "
        "window to detect material behavioral drift without model training."
    ),
    responses={
        200: {"description": "Trend and drift report generated successfully."},
        400: {"model": ErrorResponse, "description": "Invalid month format, date range, or groupBy value."},
    },
)
def get_trends_report(
    userRef: str = Path(..., description="Wallet user reference"),
    month: str | None = Query(
        default=None,
        description="Optional month in YYYY-MM format. If provided, month takes precedence over from/to.",
        examples=["2026-03"],
    ),
    from_: date | datetime | None = Query(
        default=None,
        alias="from",
        description="Start date/datetime (inclusive). Example: 2026-03-01",
        examples=["2026-03-01"],
    ),
    to_: date | datetime | None = Query(
        default=None,
        alias="to",
        description="End date/datetime (inclusive). Example: 2026-03-31",
        examples=["2026-03-31"],
    ),
    groupBy: str = Query(
        default="week",
        description="Series grouping: day, week, or month",
        examples=["week"],
    ),
    db: Session = Depends(get_db),
) -> ReportTrendsResponse:
    month_value = month.strip() if isinstance(month, str) else None
    group_by = _normalize_group_by(groupBy)
    if month_value:
        from_dt, to_dt = _resolve_month_window(month_value)
        baseline_from_dt, baseline_to_dt = _resolve_previous_month_window(month_value)
    else:
        from_dt, to_dt = _resolve_window(from_, to_)
        baseline_from_dt, baseline_to_dt = _resolve_previous_window(from_dt, to_dt)

    logger.info(
        "Trends report user_ref=%s from=%s to=%s baseline_from=%s baseline_to=%s group_by=%s",
        userRef,
        from_dt,
        to_dt,
        baseline_from_dt,
        baseline_to_dt,
        group_by,
    )
    current_transactions = fetch_transactions(db, userRef, from_dt, to_dt)
    baseline_transactions = fetch_transactions(db, userRef, baseline_from_dt, baseline_to_dt)

    return ReportTrendsResponse(
        **build_trend_report(
            user_ref=userRef,
            from_dt=from_dt,
            to_dt=to_dt,
            baseline_from_dt=baseline_from_dt,
            baseline_to_dt=baseline_to_dt,
            current_transactions=current_transactions,
            baseline_transactions=baseline_transactions,
            group_by=group_by,
        )
    )


@router.get(
    "/fhs",
    response_model=ReportFHSResponse,
    summary="Financial Health Score (0-100)",
    description=(
        "Calculates a transparent 0-100 Financial Health Score with component subscores, "
        "interpretation band, and top positive/negative drivers."
    ),
    responses={
        200: {"description": "FHS report generated successfully."},
        400: {"model": ErrorResponse, "description": "Invalid month format or date range."},
    },
)
def get_fhs_report(
    userRef: str = Path(..., description="Wallet user reference"),
    month: str | None = Query(
        default=None,
        description="Optional month in YYYY-MM format. If provided, month takes precedence over from/to.",
        examples=["2026-03"],
    ),
    from_: date | datetime | None = Query(
        default=None,
        alias="from",
        description="Start date/datetime (inclusive). Example: 2026-03-01",
        examples=["2026-03-01"],
    ),
    to_: date | datetime | None = Query(
        default=None,
        alias="to",
        description="End date/datetime (inclusive). Example: 2026-03-31",
        examples=["2026-03-31"],
    ),
    db: Session = Depends(get_db),
) -> ReportFHSResponse:
    month_value = month.strip() if isinstance(month, str) else None
    if month_value:
        from_dt, to_dt = _resolve_month_window(month_value)
    else:
        from_dt, to_dt = _resolve_window(from_, to_)

    logger.info("FHS report user_ref=%s from=%s to=%s", userRef, from_dt, to_dt)
    transactions = fetch_transactions(db, userRef, from_dt, to_dt)
    features = compute_features(transactions)
    return build_fhs(
        user_ref=userRef,
        from_dt=from_dt,
        to_dt=to_dt,
        features=features,
    )


@router.get(
    "/behavior-profile",
    response_model=ReportBehaviorProfileResponse,
    summary="Get behavioral spending profile",
    description=(
        "Assigns the user to an interpretable spending-behavior cluster using unsupervised "
        "learning on engineered financial behavior metrics."
    ),
    responses={
        200: {"description": "Behavior profile generated successfully."},
        400: {"model": ErrorResponse, "description": "Invalid month format or date range."},
    },
)
def get_behavior_profile_report(
    userRef: str = Path(..., description="Wallet user reference"),
    month: str | None = Query(
        default=None,
        description="Optional month in YYYY-MM format. If provided, month takes precedence over from/to.",
        examples=["2026-03"],
    ),
    from_: date | datetime | None = Query(
        default=None,
        alias="from",
        description="Start date/datetime (inclusive). Example: 2026-03-01",
        examples=["2026-03-01"],
    ),
    to_: date | datetime | None = Query(
        default=None,
        alias="to",
        description="End date/datetime (inclusive). Example: 2026-03-31",
        examples=["2026-03-31"],
    ),
    db: Session = Depends(get_db),
) -> ReportBehaviorProfileResponse:
    month_value = month.strip() if isinstance(month, str) else None
    if month_value:
        from_dt, to_dt = _resolve_month_window(month_value)
    else:
        from_dt, to_dt = _resolve_window(from_, to_)

    logger.info("Behavior profile report user_ref=%s from=%s to=%s", userRef, from_dt, to_dt)
    transactions = fetch_transactions(db, userRef, from_dt, to_dt)
    features = compute_features(transactions)
    return build_behavior_profile(
        user_ref=userRef,
        from_dt=from_dt,
        to_dt=to_dt,
        features=features,
    )


@router.get(
    "/recommendations",
    response_model=ReportRecommendationsResponse,
    summary="Actionable financial recommendations",
    description=(
        "Generates ranked, rule-based recommendations based on computed features and "
        "Financial Health Score drivers."
    ),
    responses={
        200: {"description": "Recommendations generated successfully."},
        400: {"model": ErrorResponse, "description": "Invalid month format or date range."},
    },
)
def get_recommendations_report(
    userRef: str = Path(..., description="Wallet user reference"),
    month: str | None = Query(
        default=None,
        description="Optional month in YYYY-MM format. If provided, month takes precedence over from/to.",
        examples=["2026-03"],
    ),
    from_: date | datetime | None = Query(
        default=None,
        alias="from",
        description="Start date/datetime (inclusive). Example: 2026-03-01",
        examples=["2026-03-01"],
    ),
    to_: date | datetime | None = Query(
        default=None,
        alias="to",
        description="End date/datetime (inclusive). Example: 2026-03-31",
        examples=["2026-03-31"],
    ),
    db: Session = Depends(get_db),
) -> ReportRecommendationsResponse:
    month_value = month.strip() if isinstance(month, str) else None
    if month_value:
        from_dt, to_dt = _resolve_month_window(month_value)
    else:
        from_dt, to_dt = _resolve_window(from_, to_)

    logger.info("Recommendations report user_ref=%s from=%s to=%s", userRef, from_dt, to_dt)
    transactions = fetch_transactions(db, userRef, from_dt, to_dt)
    features = compute_features(transactions)
    fhs_result = build_fhs(
        user_ref=userRef,
        from_dt=from_dt,
        to_dt=to_dt,
        features=features,
    )
    items = build_recommendations(features=features, fhs_result=fhs_result)

    return ReportRecommendationsResponse(
        user_ref=userRef,
        from_=from_dt,
        to=to_dt,
        fhs_score=fhs_result.score,
        interpretation=fhs_result.interpretation,
        items=items,
        generated_from=["features", "fhs"],
    )


def _generate_batch_recommendations(
    predictions: list[BatchTransactionPrediction],
) -> list[RecommendationItem]:
    if not predictions:
        return []

    high_risk = [p for p in predictions if p.predicted_is_high_risk]
    if not high_risk:
        return [
            RecommendationItem(
                title="Keep current spending behavior",
                priority="low",
                component="anomaly_risk",
                message="No high-risk transactions detected in this batch.",
                reason="Model risk scores stayed below the configured threshold.",
                estimated_impact="Maintaining similar habits should keep anomaly risk low.",
                action_type="maintain_habits",
                rank=1,
            )
        ]

    discretionary_categories = {"shopping", "entertainment", "travel", "debt"}
    discretionary_count = sum(
        1
        for p in high_risk
        if (p.category or "").strip().lower() in discretionary_categories
    )
    night_count = sum(
        1
        for p in high_risk
        if any(f.feature == "num__is_night" for f in p.xai_factors)
    )

    items: list[RecommendationItem] = []

    if discretionary_count > 0:
        items.append(
            RecommendationItem(
                title="Reduce discretionary spending",
                priority="high",
                component="non_essential_ratio",
                message="High-risk predictions are concentrated in Shopping/Entertainment/Travel. Consider reducing these by 10-15%.",
                reason="Multiple risky transactions appeared in discretionary categories.",
                estimated_impact="Lowering discretionary spend should reduce future anomaly scores.",
                action_type="reduce_spending",
                rank=0,
            )
        )

    if night_count > 0:
        items.append(
            RecommendationItem(
                title="Avoid late-night high-value spending",
                priority="medium",
                component="anomaly_risk",
                message="Several risky transactions occurred late at night. Add a budget rule for late-hour purchases.",
                reason="Night-time spending contributed to elevated model risk.",
                estimated_impact="Reducing late-night purchases can lower risk volatility.",
                action_type="stabilize_spending",
                rank=0,
            )
        )

    if not items:
        items.append(
            RecommendationItem(
                title="Review high-risk transactions",
                priority="medium",
                component="anomaly_risk",
                message="Review these transactions and avoid repeating similar high-risk patterns.",
                reason="The model flagged one or more transactions as high risk.",
                estimated_impact="Behavioral adjustments can improve risk outcomes.",
                action_type="review_anomalies",
                rank=0,
            )
        )

    for idx, item in enumerate(items, start=1):
        item.rank = idx

    return items


@router.post(
    "/anomaly-predict",
    response_model=ReportAnomalyPredictResponse,
    summary="Predict anomaly risk for one transaction",
    description="Scores one transaction using the trained anomaly model and returns top xAI factors.",
)
def predict_anomaly_report(
    payload: AnomalyPredictRequest,
    userRef: str = Path(..., description="Wallet user reference"),
    db: Session = Depends(get_db),
) -> ReportAnomalyPredictResponse:
    history_transactions = (
        db.query(Transaction)
        .filter(Transaction.user_ref == userRef)
        .order_by(Transaction.occurred_at.asc(), Transaction.created_at.asc())
        .all()
    )

    result = predict_transaction_risks(
        user_ref=userRef,
        history_transactions=history_transactions,
        candidate_transactions=[
            {
                "occurred_at": payload.occurred_at,
                "amount": payload.amount,
                "direction": payload.direction,
                "category": payload.category,
                "description": payload.description,
                "currency": payload.currency,
            }
        ],
    )

    predictions = result.get("predictions", [])
    if not predictions:
        return ReportAnomalyPredictResponse(
            user_ref=userRef,
            occurred_at=payload.occurred_at,
            amount=payload.amount,
            risk_score=0.0,
            threshold=float(result.get("threshold", 0.5)),
            predicted_is_high_risk=False,
            model_available=bool(result.get("model_available", False)),
            model_name=result.get("model_name"),
            xai_factors=[],
        )

    predicted = predictions[0]
    xai_factors = [PredictionXAIFactor(**f) for f in predicted.get("xai_factors", [])]
    return ReportAnomalyPredictResponse(
        user_ref=userRef,
        occurred_at=predicted["occurred_at"],
        amount=Decimal(predicted["amount"]),
        risk_score=float(predicted["risk_score"]),
        threshold=float(result.get("threshold", 0.5)),
        predicted_is_high_risk=bool(predicted["predicted_is_high_risk"]),
        model_available=bool(result.get("model_available", False)),
        model_name=result.get("model_name"),
        xai_factors=xai_factors,
    )


@router.post(
    "/anomaly-predict-batch",
    response_model=BatchAnomalyPredictResponse,
    summary="Predict anomaly risk for multiple transactions",
    description="Scores a batch of transactions and returns per-transaction xAI factors and recommendations.",
)
def predict_anomaly_batch_report(
    payload: BatchAnomalyPredictRequest,
    userRef: str = Path(..., description="Wallet user reference"),
    db: Session = Depends(get_db),
) -> BatchAnomalyPredictResponse:
    history_transactions = (
        db.query(Transaction)
        .filter(Transaction.user_ref == userRef)
        .order_by(Transaction.occurred_at.asc(), Transaction.created_at.asc())
        .all()
    )

    result = predict_transaction_risks(
        user_ref=userRef,
        history_transactions=history_transactions,
        candidate_transactions=[
            {
                "occurred_at": tx.occurred_at,
                "amount": tx.amount,
                "direction": tx.direction,
                "category": tx.category,
                "description": tx.description,
                "currency": tx.currency,
            }
            for tx in payload.transactions
        ],
    )

    predictions = [
        BatchTransactionPrediction(
            index=int(item["index"]),
            occurred_at=item["occurred_at"],
            amount=Decimal(item["amount"]),
            direction=item["direction"],
            category=item.get("category"),
            risk_score=float(item["risk_score"]),
            predicted_is_high_risk=bool(item["predicted_is_high_risk"]),
            xai_factors=[PredictionXAIFactor(**factor) for factor in item.get("xai_factors", [])],
        )
        for item in result.get("predictions", [])
    ]

    recommendations = _generate_batch_recommendations(predictions)
    return BatchAnomalyPredictResponse(
        user_ref=userRef,
        threshold=float(result.get("threshold", 0.5)),
        model_available=bool(result.get("model_available", False)),
        model_name=result.get("model_name"),
        predictions=predictions,
        recommendations=recommendations,
    )
