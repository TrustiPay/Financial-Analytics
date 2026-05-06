from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "from must be earlier than or equal to to",
                "code": "VALIDATION_ERROR",
            }
        }
    )

    detail: str
    code: str | None = None


class IngestTransaction(BaseModel):
    external_tx_id: str = Field(min_length=1)
    user_ref: str = Field(min_length=1)
    occurred_at: datetime
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    direction: str
    category: str | None = None
    description: str | None = None
    currency: str | None = None

    @field_validator("external_tx_id", "user_ref", mode="before")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if value is None or not isinstance(value, str):
            raise ValueError("must not be empty")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("direction", mode="before")
    @classmethod
    def validate_direction_value(cls, value: str) -> str:
        if value is None or not isinstance(value, str):
            raise ValueError("direction is required")
        cleaned = value.strip().lower()
        if cleaned not in {"income", "expense", "debit", "credit"}:
            raise ValueError("direction must be one of income, expense, debit, credit")
        return cleaned


class IngestTransactionsRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "wallet",
                "transactions": [
                    {
                        "external_tx_id": "WALLET-1001",
                        "user_ref": "user-123",
                        "occurred_at": "2026-03-05T10:30:00Z",
                        "amount": "2500.00",
                        "direction": "debit",
                        "category": "Food",
                        "description": "Lunch",
                        "currency": "LKR",
                    },
                    {
                        "external_tx_id": "WALLET-1002",
                        "user_ref": "user-123",
                        "occurred_at": "2026-03-05T16:10:00Z",
                        "amount": "12000.00",
                        "direction": "credit",
                        "category": "Salary",
                        "description": "Monthly salary",
                        "currency": "LKR",
                    },
                ],
            }
        }
    )

    source: str = "wallet"
    transactions: list[IngestTransaction] = Field(min_length=1)


class IngestErrorItem(BaseModel):
    external_tx_id: str | None = None
    message: str


class IngestTransactionsResponse(BaseModel):
    received: int
    inserted: int
    duplicates: int
    failed: int
    errors: list[IngestErrorItem] = Field(default_factory=list)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_ref: str
    source: str
    external_tx_id: str
    occurred_at: datetime
    amount: Decimal
    direction: str
    category: str | None
    description: str | None
    currency: str | None
    created_at: datetime


class UserRefItem(BaseModel):
    user_ref: str


class UsersListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {"user_ref": "demo-user-001"},
                    {"user_ref": "demo-user-002"},
                ],
                "count": 2,
            }
        }
    )

    items: list[UserRefItem] = Field(default_factory=list)
    count: int


class PagedTransactionsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "a53c27b8-4cb4-41fe-b281-b89f2423c307",
                        "user_ref": "user-123",
                        "source": "wallet",
                        "external_tx_id": "WALLET-1002",
                        "occurred_at": "2026-03-05T16:10:00Z",
                        "amount": "12000.00",
                        "direction": "income",
                        "category": "Salary",
                        "description": "Monthly salary",
                        "currency": "LKR",
                        "created_at": "2026-03-05T16:11:15Z",
                    }
                ],
                "limit": 50,
                "offset": 0,
                "count": 1,
                "total": 12,
            }
        }
    )

    items: list[TransactionOut] = Field(default_factory=list)
    limit: int
    offset: int
    count: int
    total: int


class SummaryPoint(BaseModel):
    period: str
    income: Decimal
    expense: Decimal
    net: Decimal


class ReportSummaryResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "user_ref": "user-123",
                "from": "2026-03-01T00:00:00Z",
                "to": "2026-03-31T23:59:59.999999Z",
                "group_by": "month",
                "income_total": "12000.00",
                "expense_total": "3500.00",
                "net_total": "8500.00",
                "series": [
                    {
                        "period": "2026-03",
                        "income": "12000.00",
                        "expense": "3500.00",
                        "net": "8500.00",
                    }
                ],
            }
        },
    )

    user_ref: str
    from_: datetime = Field(alias="from")
    to: datetime
    group_by: str
    income_total: Decimal
    expense_total: Decimal
    net_total: Decimal
    series: list[SummaryPoint] = Field(default_factory=list)


class CategoryTotal(BaseModel):
    category: str
    expense_total: Decimal
    transaction_count: int


class ReportCategoriesResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "user_ref": "user-123",
                "from": "2026-03-01T00:00:00Z",
                "to": "2026-03-31T23:59:59.999999Z",
                "items": [
                    {
                        "category": "Food",
                        "expense_total": "2500.00",
                        "transaction_count": 3,
                    },
                    {
                        "category": "Uncategorized",
                        "expense_total": "1000.00",
                        "transaction_count": 1,
                    },
                ],
                "expense_total": "3500.00",
            }
        },
    )

    user_ref: str
    from_: datetime = Field(alias="from")
    to: datetime
    items: list[CategoryTotal] = Field(default_factory=list)
    expense_total: Decimal


class AnomalyItem(BaseModel):
    type: str
    occurred_at: datetime | None = None
    period: str | None = None
    transaction_id: str | None = None
    external_tx_id: str | None = None
    amount: Decimal | None = None
    direction: str | None = None
    category: str | None = None
    description: str | None = None
    score: float
    reason: str


class ReportAnomaliesResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "user_ref": "user-123",
                "from": "2026-03-01T00:00:00Z",
                "to": "2026-03-31T23:59:59.999999Z",
                "anomaly_count": 2,
                "items": [
                    {
                        "type": "transaction_outlier",
                        "occurred_at": "2026-03-20T11:30:00Z",
                        "period": None,
                        "transaction_id": "2337cbf4-99ed-4f94-b351-2a760f39f45e",
                        "external_tx_id": "WALLET-2005",
                        "amount": "9500.00",
                        "direction": "expense",
                        "category": "Shopping",
                        "description": "Laptop purchase",
                        "score": 2.91,
                        "reason": "Transaction amount is unusually high (z=2.91) compared to your typical expenses in this period.",
                    },
                    {
                        "type": "weekly_spike",
                        "occurred_at": "2026-03-16T00:00:00Z",
                        "period": "2026-W12",
                        "transaction_id": None,
                        "external_tx_id": None,
                        "amount": "14500.00",
                        "direction": "expense",
                        "category": None,
                        "description": None,
                        "score": 2.66,
                        "reason": "Weekly spending total is unusually high (z=2.66) compared to other weeks in the selected period.",
                    },
                ],
            }
        },
    )

    user_ref: str
    from_: datetime = Field(alias="from")
    to: datetime
    anomaly_count: int
    items: list[AnomalyItem] = Field(default_factory=list)


class AnomalyImpactTransaction(BaseModel):
    id: str
    external_tx_id: str
    occurred_at: datetime
    amount: Decimal
    category: str | None = None
    description: str | None = None


class ReportAnomalyImpactResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "user_ref": "user-123",
                "from": "2026-04-01T00:00:00Z",
                "to": "2026-04-30T23:59:59.999999Z",
                "income_total": "150000.00",
                "expense_total": "430000.00",
                "actual_net_total": "-280000.00",
                "anomaly_expense_total": "350000.00",
                "normal_expense_total": "80000.00",
                "normal_essential_expense_total": "62000.00",
                "normal_non_essential_expense_total": "18000.00",
                "routine_net_total": "70000.00",
                "anomaly_count": 1,
                "weekly_volatility": 0.22,
                "stability_buffer": "1760.00",
                "monthly_recovery_capacity": "70940.00",
                "estimated_recovery_months": 5,
                "recommended_non_essential_cut": "2700.00",
                "summary": "Routine spending remains manageable after isolating anomaly expenses.",
                "actions": [
                    "Treat anomaly expenses as exceptional shock items, not routine spending.",
                    "Keep essential expenses separate from discretionary reductions.",
                ],
                "anomaly_transactions": [
                    {
                        "id": "2337cbf4-99ed-4f94-b351-2a760f39f45e",
                        "external_tx_id": "WALLET-2005",
                        "occurred_at": "2026-04-24T23:45:00Z",
                        "amount": "350000.00",
                        "category": "Shopping",
                        "description": "Unexpected high-value luxury purchase",
                    }
                ],
            }
        },
    )

    user_ref: str
    from_: datetime = Field(alias="from")
    to: datetime
    income_total: Decimal
    expense_total: Decimal
    actual_net_total: Decimal
    anomaly_expense_total: Decimal
    normal_expense_total: Decimal
    normal_essential_expense_total: Decimal
    normal_non_essential_expense_total: Decimal
    routine_net_total: Decimal
    anomaly_count: int
    weekly_volatility: float
    stability_buffer: Decimal
    monthly_recovery_capacity: Decimal
    estimated_recovery_months: int | None
    recommended_non_essential_cut: Decimal
    summary: str
    actions: list[str] = Field(default_factory=list)
    anomaly_transactions: list[AnomalyImpactTransaction] = Field(default_factory=list)


class AnomalyPredictRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "occurred_at": "2026-03-20T11:30:00Z",
                "amount": "9500.00",
                "direction": "expense",
                "category": "Shopping",
                "description": "Laptop purchase",
                "currency": "LKR",
            }
        }
    )

    occurred_at: datetime
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    direction: str = "expense"
    category: str | None = None
    description: str | None = None
    currency: str | None = None

    @field_validator("direction", mode="before")
    @classmethod
    def validate_direction_value(cls, value: str) -> str:
        if value is None or not isinstance(value, str):
            raise ValueError("direction is required")
        cleaned = value.strip().lower()
        if cleaned not in {"income", "expense", "debit", "credit"}:
            raise ValueError("direction must be one of income, expense, debit, credit")
        return cleaned


class PredictionXAIFactor(BaseModel):
    feature: str
    contribution: float
    effect: str


class RecommendationItem(BaseModel):
    title: str
    priority: str
    component: str
    message: str
    reason: str
    estimated_impact: str | None = None
    action_type: str | None = None
    rank: int


class ReportAnomalyPredictResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_ref": "demo-user-001",
                "occurred_at": "2026-03-20T11:30:00Z",
                "amount": "9500.00",
                "risk_score": 0.84,
                "threshold": 0.42,
                "predicted_is_high_risk": True,
                "model_available": True,
                "model_name": "Pipeline",
                "xai_factors": [
                    {
                        "feature": "num__amount",
                        "contribution": 0.54,
                        "effect": "risk_up",
                    },
                    {
                        "feature": "num__amount_to_user_avg_ratio",
                        "contribution": 0.42,
                        "effect": "risk_up",
                    },
                ],
            }
        }
    )

    user_ref: str
    occurred_at: datetime
    amount: Decimal
    risk_score: float
    threshold: float
    predicted_is_high_risk: bool
    model_available: bool
    model_name: str | None = None
    xai_factors: list[PredictionXAIFactor] = Field(default_factory=list)


class BatchAnomalyPredictRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "transactions": [
                    {
                        "occurred_at": "2026-03-20T11:30:00Z",
                        "amount": "9500.00",
                        "direction": "expense",
                        "category": "Shopping",
                        "description": "Laptop purchase",
                        "currency": "LKR",
                    },
                    {
                        "occurred_at": "2026-03-20T23:00:00Z",
                        "amount": "5000.00",
                        "direction": "expense",
                        "category": "Entertainment",
                        "description": "Concert ticket",
                        "currency": "LKR",
                    },
                ]
            }
        }
    )

    transactions: list[AnomalyPredictRequest] = Field(min_length=1, max_length=50)


class BatchTransactionPrediction(BaseModel):
    index: int
    occurred_at: datetime
    amount: Decimal
    direction: str
    category: str | None
    risk_score: float
    predicted_is_high_risk: bool
    xai_factors: list[PredictionXAIFactor] = Field(default_factory=list)


class BatchAnomalyPredictResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_ref": "demo-user-001",
                "threshold": 0.42,
                "model_available": True,
                "model_name": "Pipeline",
                "predictions": [
                    {
                        "index": 0,
                        "occurred_at": "2026-03-20T11:30:00Z",
                        "amount": "9500.00",
                        "direction": "expense",
                        "category": "Shopping",
                        "risk_score": 0.84,
                        "predicted_is_high_risk": True,
                        "xai_factors": [
                            {"feature": "num__amount", "contribution": 0.54, "effect": "risk_up"}
                        ],
                    },
                    {
                        "index": 1,
                        "occurred_at": "2026-03-20T23:00:00Z",
                        "amount": "5000.00",
                        "direction": "expense",
                        "category": "Entertainment",
                        "risk_score": 0.68,
                        "predicted_is_high_risk": True,
                        "xai_factors": [
                            {"feature": "num__is_night", "contribution": 0.42, "effect": "risk_up"}
                        ],
                    },
                ],
                "recommendations": [
                    {
                        "title": "Reduce discretionary spending",
                        "priority": "high",
                        "component": "non_essential_ratio",
                        "message": "Consider reducing Shopping and Entertainment expenses by 10-15%.",
                        "reason": "High discretionary spending detected in batch.",
                        "estimated_impact": "Reducing these expenses could lower your risk profile.",
                        "action_type": "reduce_spending",
                        "rank": 1,
                    }
                ],
            }
        }
    )

    user_ref: str
    threshold: float
    model_available: bool
    model_name: str | None = None
    predictions: list[BatchTransactionPrediction] = Field(default_factory=list)
    recommendations: list[RecommendationItem] = Field(default_factory=list)


class ReportFeaturesResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "user_ref": "user-123",
                "from": "2026-03-01T00:00:00Z",
                "to": "2026-03-31T23:59:59.999999Z",
                "income_total": "12000.00",
                "expense_total": "3500.00",
                "net_total": "8500.00",
                "savings_ratio": 0.7083,
                "non_essential_ratio": 0.4286,
                "weekly_expense_mean": 875.0,
                "weekly_expense_std": 315.0,
                "spending_stability": 0.36,
                "expense_tx_count": 6,
                "weeks_count": 4,
                "spending_frequency": 1.5,
                "anomaly_count": 1,
                "anomaly_rate_per_100_tx": 10.0,
                "non_essential_expense_total": "1500.00",
                "essential_expense_total": "2000.00",
            }
        },
    )

    user_ref: str
    from_: datetime = Field(alias="from")
    to: datetime
    income_total: Decimal
    expense_total: Decimal
    net_total: Decimal
    savings_ratio: float | None
    non_essential_ratio: float | None
    weekly_expense_mean: float | None
    weekly_expense_std: float | None
    spending_stability: float | None
    expense_tx_count: int
    weeks_count: int
    spending_frequency: float
    anomaly_count: int
    anomaly_rate_per_100_tx: float
    non_essential_expense_total: Decimal
    essential_expense_total: Decimal


class TrendSeriesPoint(BaseModel):
    period: str
    income: Decimal
    expense: Decimal
    net: Decimal
    expense_tx_count: int
    anomaly_count: int


class DriftMetricItem(BaseModel):
    metric: str
    label: str
    unit: str
    direction: str
    impact: str
    severity: str
    current_value: float | None
    baseline_value: float | None
    absolute_change: float | None
    relative_change: float | None
    summary: str


class TrendFeatureSnapshot(BaseModel):
    income_total: Decimal
    expense_total: Decimal
    net_total: Decimal
    savings_ratio: float | None
    non_essential_ratio: float | None
    weekly_expense_mean: float | None
    spending_frequency: float
    spending_stability: float | None
    anomaly_rate_per_100_tx: float


class ReportTrendsResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "user_ref": "user-123",
                "from": "2026-03-08T00:00:00Z",
                "to": "2026-03-14T23:59:59.999999Z",
                "group_by": "week",
                "baseline_from": "2026-03-01T00:00:00Z",
                "baseline_to": "2026-03-07T23:59:59.999999Z",
                "baseline_available": True,
                "summary": "Material drift was detected versus the prior period. Total expense increased from 3000.00 to 5200.00 versus the prior period (+73.3%).",
                "drift_detected": True,
                "current_snapshot": {
                    "income_total": "10000.00",
                    "expense_total": "5200.00",
                    "net_total": "4800.00",
                    "savings_ratio": 0.48,
                    "non_essential_ratio": 0.58,
                    "weekly_expense_mean": 5200.0,
                    "spending_frequency": 4.0,
                    "spending_stability": 0.0,
                    "anomaly_rate_per_100_tx": 25.0,
                },
                "baseline_snapshot": {
                    "income_total": "10000.00",
                    "expense_total": "3000.00",
                    "net_total": "7000.00",
                    "savings_ratio": 0.70,
                    "non_essential_ratio": 0.20,
                    "weekly_expense_mean": 3000.0,
                    "spending_frequency": 2.0,
                    "spending_stability": 0.0,
                    "anomaly_rate_per_100_tx": 0.0,
                },
                "series": [
                    {
                        "period": "2026-W11",
                        "income": "10000.00",
                        "expense": "5200.00",
                        "net": "4800.00",
                        "expense_tx_count": 4,
                        "anomaly_count": 1,
                    }
                ],
                "drift_items": [
                    {
                        "metric": "expense_total",
                        "label": "Total expense",
                        "unit": "currency",
                        "direction": "up",
                        "impact": "risk_up",
                        "severity": "high",
                        "current_value": 5200.0,
                        "baseline_value": 3000.0,
                        "absolute_change": 2200.0,
                        "relative_change": 0.7333,
                        "summary": "Total expense increased from 3000.00 to 5200.00 versus the prior period (+73.3%).",
                    }
                ],
            }
        },
    )

    user_ref: str
    from_: datetime = Field(alias="from")
    to: datetime
    group_by: str
    baseline_from_: datetime = Field(alias="baseline_from")
    baseline_to: datetime = Field(alias="baseline_to")
    baseline_available: bool
    summary: str
    drift_detected: bool
    current_snapshot: TrendFeatureSnapshot
    baseline_snapshot: TrendFeatureSnapshot | None = None
    series: list[TrendSeriesPoint] = Field(default_factory=list)
    drift_items: list[DriftMetricItem] = Field(default_factory=list)


class FHSSubscore(BaseModel):
    name: str
    score: float
    max_score: float
    value: float | None
    status: str
    reason: str


class FHSDriver(BaseModel):
    type: str
    component: str
    message: str


class FHSFeatureSnapshot(BaseModel):
    income_total: Decimal
    expense_total: Decimal
    net_total: Decimal
    savings_ratio: float | None
    non_essential_ratio: float | None
    spending_stability: float | None
    anomaly_rate_per_100_tx: float


class ReportFHSResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "user_ref": "user-123",
                "from": "2026-03-01T00:00:00Z",
                "to": "2026-03-31T23:59:59.999999Z",
                "score": 78.0,
                "max_score": 100.0,
                "interpretation": "Stable",
                "summary": "Your finances look generally stable, with room for improvement.",
                "subscores": [
                    {
                        "name": "Savings Ratio",
                        "score": 30.0,
                        "max_score": 35.0,
                        "value": 0.28,
                        "status": "strong",
                        "reason": "You saved a healthy share of your income during this period.",
                    },
                    {
                        "name": "Non-Essential Spending",
                        "score": 17.0,
                        "max_score": 25.0,
                        "value": 0.34,
                        "status": "moderate",
                        "reason": "A moderate share of your expenses were discretionary.",
                    },
                ],
                "top_drivers": [
                    {
                        "type": "positive",
                        "component": "Savings Ratio",
                        "message": "Your savings ratio improved your score.",
                    },
                    {
                        "type": "negative",
                        "component": "Spending Stability",
                        "message": "Weekly spending volatility reduced your score.",
                    },
                ],
                "feature_snapshot": {
                    "income_total": "12000.00",
                    "expense_total": "8700.00",
                    "net_total": "3300.00",
                    "savings_ratio": 0.275,
                    "non_essential_ratio": 0.34,
                    "spending_stability": 0.52,
                    "anomaly_rate_per_100_tx": 8.33,
                },
            }
        },
    )

    user_ref: str
    from_: datetime = Field(alias="from")
    to: datetime
    score: float
    max_score: float
    interpretation: str
    summary: str
    subscores: list[FHSSubscore] = Field(default_factory=list)
    top_drivers: list[FHSDriver] = Field(default_factory=list)
    feature_snapshot: FHSFeatureSnapshot


class BehaviorFeatureVector(BaseModel):
    savings_ratio: float
    non_essential_ratio: float
    spending_stability: float
    anomaly_rate_per_100_tx: float


class ReportBehaviorProfileResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "user_ref": "demo-user-001",
                "from": "2026-03-01T00:00:00Z",
                "to": "2026-03-31T23:59:59.999999Z",
                "profile": "Lifestyle Spender",
                "cluster_id": 2,
                "distance_to_centroid": 0.41,
                "feature_vector": {
                    "savings_ratio": 0.08,
                    "non_essential_ratio": 0.46,
                    "spending_stability": 0.62,
                    "anomaly_rate_per_100_tx": 9.1,
                },
                "explanation": (
                    "This profile reflects lower savings and a higher share of discretionary "
                    "spending, often associated with lifestyle-driven expense patterns."
                ),
            }
        },
    )

    user_ref: str
    from_: datetime = Field(alias="from")
    to: datetime
    profile: str
    cluster_id: int
    distance_to_centroid: float
    feature_vector: BehaviorFeatureVector
    explanation: str


class ReportRecommendationsResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "user_ref": "user-123",
                "from": "2026-03-01T00:00:00Z",
                "to": "2026-03-31T23:59:59.999999Z",
                "fhs_score": 54.0,
                "interpretation": "Moderate",
                "items": [
                    {
                        "title": "Improve monthly savings",
                        "priority": "high",
                        "component": "savings_ratio",
                        "message": "Try to keep at least 10% of your income unspent each month.",
                        "reason": "Your savings ratio is currently low, which significantly reduced your score.",
                        "estimated_impact": "Increasing savings above 10% could improve your savings subscore.",
                        "action_type": "increase_savings",
                        "rank": 1,
                    },
                    {
                        "title": "Reduce discretionary spending",
                        "priority": "medium",
                        "component": "non_essential_ratio",
                        "message": "A large share of your spending is discretionary. Reduce shopping or entertainment expenses by 10-15%.",
                        "reason": "High discretionary spending lowered your non-essential spending score.",
                        "estimated_impact": "Reducing non-essential spending by about 10% may improve your score and free more money for savings.",
                        "action_type": "reduce_spending",
                        "rank": 2,
                    },
                ],
                "generated_from": ["features", "fhs"],
            }
        },
    )

    user_ref: str
    from_: datetime = Field(alias="from")
    to: datetime
    fhs_score: float
    interpretation: str
    items: list[RecommendationItem] = Field(default_factory=list)
    generated_from: list[str] = Field(default_factory=lambda: ["features", "fhs"])
