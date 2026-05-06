from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.models import Transaction
from app.services.anomalies import detect_anomalies
from app.services.features import compute_features

GroupBy = Literal["day", "week", "month"]


@dataclass(frozen=True)
class DriftRule:
    metric: str
    label: str
    unit: str
    mode: str
    low: float
    medium: float
    high: float
    risk_on_increase: bool
    zero_floor: float = 0.0


DRIFT_RULES: tuple[DriftRule, ...] = (
    DriftRule(
        metric="expense_total",
        label="Total expense",
        unit="currency",
        mode="relative",
        low=0.25,
        medium=0.40,
        high=0.60,
        risk_on_increase=True,
        zero_floor=500.0,
    ),
    DriftRule(
        metric="savings_ratio",
        label="Savings ratio",
        unit="ratio",
        mode="absolute",
        low=0.10,
        medium=0.15,
        high=0.20,
        risk_on_increase=False,
    ),
    DriftRule(
        metric="non_essential_ratio",
        label="Non-essential spending share",
        unit="ratio",
        mode="absolute",
        low=0.12,
        medium=0.18,
        high=0.24,
        risk_on_increase=True,
    ),
    DriftRule(
        metric="spending_frequency",
        label="Spending frequency",
        unit="frequency",
        mode="relative",
        low=0.35,
        medium=0.55,
        high=0.80,
        risk_on_increase=True,
        zero_floor=1.0,
    ),
    DriftRule(
        metric="spending_stability",
        label="Spending volatility",
        unit="ratio",
        mode="absolute",
        low=0.15,
        medium=0.25,
        high=0.35,
        risk_on_increase=True,
    ),
    DriftRule(
        metric="anomaly_rate_per_100_tx",
        label="Anomaly rate",
        unit="rate",
        mode="absolute",
        low=5.0,
        medium=8.0,
        high=12.0,
        risk_on_increase=True,
    ),
)

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


def build_trend_report(
    *,
    user_ref: str,
    from_dt: datetime,
    to_dt: datetime,
    baseline_from_dt: datetime,
    baseline_to_dt: datetime,
    current_transactions: list[Transaction],
    baseline_transactions: list[Transaction],
    group_by: GroupBy,
) -> dict:
    current_features = compute_features(current_transactions)
    baseline_available = bool(baseline_transactions)
    baseline_features = compute_features(baseline_transactions) if baseline_available else None

    drift_items = _compute_drift_items(current_features, baseline_features) if baseline_features else []
    return {
        "user_ref": user_ref,
        "from": from_dt,
        "to": to_dt,
        "group_by": group_by,
        "baseline_from": baseline_from_dt,
        "baseline_to": baseline_to_dt,
        "baseline_available": baseline_available,
        "summary": _build_overall_summary(
            current_transactions=current_transactions,
            baseline_transactions=baseline_transactions,
            drift_items=drift_items,
        ),
        "drift_detected": bool(drift_items),
        "current_snapshot": _build_snapshot(current_features),
        "baseline_snapshot": _build_snapshot(baseline_features) if baseline_features else None,
        "series": compute_trend_series(current_transactions, group_by),
        "drift_items": drift_items,
    }


def compute_trend_series(
    transactions: list[Transaction],
    group_by: GroupBy,
) -> list[dict]:
    buckets: dict[str, dict] = {}
    bucket_sort_keys: dict[str, tuple[int, ...]] = {}

    for tx in transactions:
        period, sort_key = _bucket_for(tx.occurred_at, group_by)
        if period not in buckets:
            buckets[period] = {
                "income": Decimal("0"),
                "expense": Decimal("0"),
                "expense_tx_count": 0,
                "transactions": [],
            }
            bucket_sort_keys[period] = sort_key

        amount = Decimal(tx.amount)
        direction = tx.direction.lower()
        if direction == "income":
            buckets[period]["income"] += amount
        elif direction == "expense":
            buckets[period]["expense"] += amount
            buckets[period]["expense_tx_count"] += 1

        buckets[period]["transactions"].append(tx)

    series: list[dict] = []
    for period in sorted(buckets.keys(), key=lambda value: bucket_sort_keys[value]):
        bucket = buckets[period]
        income = bucket["income"]
        expense = bucket["expense"]
        bucket_transactions = bucket["transactions"]
        series.append(
            {
                "period": period,
                "income": income,
                "expense": expense,
                "net": income - expense,
                "expense_tx_count": int(bucket["expense_tx_count"]),
                "anomaly_count": len(detect_anomalies(bucket_transactions)),
            }
        )

    return series


def _build_snapshot(features: dict | None) -> dict | None:
    if not features:
        return None
    return {
        "income_total": features["income_total"],
        "expense_total": features["expense_total"],
        "net_total": features["net_total"],
        "savings_ratio": features["savings_ratio"],
        "non_essential_ratio": features["non_essential_ratio"],
        "weekly_expense_mean": features["weekly_expense_mean"],
        "spending_frequency": features["spending_frequency"],
        "spending_stability": features["spending_stability"],
        "anomaly_rate_per_100_tx": features["anomaly_rate_per_100_tx"],
    }


def _compute_drift_items(
    current_features: dict,
    baseline_features: dict | None,
) -> list[dict]:
    if not baseline_features:
        return []

    scored_items: list[tuple[int, float, dict]] = []
    for rule in DRIFT_RULES:
        item = _evaluate_rule(
            rule=rule,
            current_value=_as_float(current_features.get(rule.metric)),
            baseline_value=_as_float(baseline_features.get(rule.metric)),
        )
        if item is None:
            continue
        magnitude = abs(item["relative_change"]) if item["relative_change"] is not None else abs(item["absolute_change"])
        scored_items.append((SEVERITY_RANK[item["severity"]], magnitude, item))

    scored_items.sort(key=lambda value: (value[0], value[1]), reverse=True)
    return [item for _, _, item in scored_items]


def _evaluate_rule(
    *,
    rule: DriftRule,
    current_value: float | None,
    baseline_value: float | None,
) -> dict | None:
    if current_value is None or baseline_value is None:
        return None

    absolute_change = current_value - baseline_value
    if abs(absolute_change) < 1e-9:
        return None

    relative_change: float | None = None
    magnitude = 0.0

    if rule.mode == "relative":
        if abs(baseline_value) >= 1e-9:
            relative_change = absolute_change / abs(baseline_value)
            magnitude = abs(relative_change)
            if magnitude < rule.low:
                return None
        elif abs(current_value) >= rule.zero_floor:
            magnitude = 1.0
        else:
            return None
    else:
        magnitude = abs(absolute_change)
        if magnitude < rule.low:
            return None
        if abs(baseline_value) >= 1e-9:
            relative_change = absolute_change / abs(baseline_value)

    severity = _severity_for(rule, magnitude)
    direction = "up" if absolute_change > 0 else "down"
    impact = _impact_for(rule, direction)

    return {
        "metric": rule.metric,
        "label": rule.label,
        "unit": rule.unit,
        "direction": direction,
        "impact": impact,
        "severity": severity,
        "current_value": round(current_value, 4),
        "baseline_value": round(baseline_value, 4),
        "absolute_change": round(absolute_change, 4),
        "relative_change": round(relative_change, 4) if relative_change is not None else None,
        "summary": _build_item_summary(
            rule=rule,
            current_value=current_value,
            baseline_value=baseline_value,
            absolute_change=absolute_change,
            relative_change=relative_change,
        ),
    }


def _severity_for(rule: DriftRule, magnitude: float) -> str:
    if magnitude >= rule.high:
        return "high"
    if magnitude >= rule.medium:
        return "medium"
    return "low"


def _impact_for(rule: DriftRule, direction: str) -> str:
    moving_up = direction == "up"
    if rule.risk_on_increase:
        return "risk_up" if moving_up else "risk_down"
    return "risk_down" if moving_up else "risk_up"


def _build_item_summary(
    *,
    rule: DriftRule,
    current_value: float,
    baseline_value: float,
    absolute_change: float,
    relative_change: float | None,
) -> str:
    change_word = "increased" if absolute_change > 0 else "decreased"

    if rule.unit == "ratio":
        return (
            f"{rule.label} {change_word} from {_format_value(rule.unit, baseline_value)} "
            f"to {_format_value(rule.unit, current_value)} versus the prior period "
            f"({_format_ratio_points(absolute_change)})."
        )

    if relative_change is not None:
        return (
            f"{rule.label} {change_word} from {_format_value(rule.unit, baseline_value)} "
            f"to {_format_value(rule.unit, current_value)} versus the prior period "
            f"({relative_change:+.1%})."
        )

    return (
        f"{rule.label} {change_word} from {_format_value(rule.unit, baseline_value)} "
        f"to {_format_value(rule.unit, current_value)} versus the prior period."
    )


def _build_overall_summary(
    *,
    current_transactions: list[Transaction],
    baseline_transactions: list[Transaction],
    drift_items: list[dict],
) -> str:
    if not current_transactions and not baseline_transactions:
        return "No transaction data is available for trend analysis."
    if not baseline_transactions:
        return "Current trends are available, but there is not enough prior history to assess drift."
    if not current_transactions:
        return "No transactions were recorded in the selected window."
    if not drift_items:
        return "No material drift was detected versus the prior period."

    highlights = " ".join(item["summary"] for item in drift_items[:2])
    return f"Material drift was detected versus the prior period. {highlights}"


def _bucket_for(
    occurred_at: datetime,
    group_by: GroupBy,
) -> tuple[str, tuple[int, ...]]:
    if group_by == "day":
        date_value = occurred_at.date()
        return date_value.isoformat(), (date_value.year, date_value.month, date_value.day)
    if group_by == "month":
        return occurred_at.strftime("%Y-%m"), (occurred_at.year, occurred_at.month)

    iso_year, iso_week, _ = occurred_at.isocalendar()
    return f"{iso_year}-W{iso_week:02d}", (iso_year, iso_week)


def _as_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _format_value(unit: str, value: float) -> str:
    if unit == "currency":
        return f"{value:,.2f}"
    if unit == "ratio":
        return f"{value:.1%}"
    if unit == "rate":
        return f"{value:.1f} per 100 tx"
    if unit == "frequency":
        return f"{value:.2f} tx/week"
    return f"{value:.2f}"


def _format_ratio_points(value: float) -> str:
    return f"{value * 100:+.1f} pts"
