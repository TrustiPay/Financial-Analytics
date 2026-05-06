from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from statistics import mean, pstdev

from app.models import Transaction
from app.services.anomalies import detect_anomalies
from app.services.features import NON_ESSENTIAL_CATEGORIES


def build_anomaly_impact(transactions: list[Transaction]) -> dict:
    income_txs = [tx for tx in transactions if tx.direction.lower() == "income"]
    expense_txs = [tx for tx in transactions if tx.direction.lower() == "expense"]

    income_total = _sum_amounts(income_txs)
    expense_total = _sum_amounts(expense_txs)
    actual_net_total = income_total - expense_total

    anomaly_items = detect_anomalies(transactions)
    anomaly_tx_ids = {
        item.get("transaction_id")
        for item in anomaly_items
        if item.get("transaction_id") and item.get("direction") == "expense"
    }
    anomaly_external_ids = {
        item.get("external_tx_id")
        for item in anomaly_items
        if item.get("external_tx_id") and item.get("direction") == "expense"
    }

    anomaly_txs = [
        tx
        for tx in expense_txs
        if tx.id in anomaly_tx_ids or tx.external_tx_id in anomaly_external_ids
    ]
    anomaly_expense_total = _sum_amounts(anomaly_txs)
    normal_expense_txs = [
        tx
        for tx in expense_txs
        if tx.id not in anomaly_tx_ids and tx.external_tx_id not in anomaly_external_ids
    ]
    normal_expense_total = _sum_amounts(normal_expense_txs)
    routine_net_total = income_total - normal_expense_total

    normal_non_essential_total = _sum_amounts(
        tx for tx in normal_expense_txs if _is_non_essential(tx.category)
    )
    normal_essential_total = normal_expense_total - normal_non_essential_total
    recommended_non_essential_cut = _recommended_non_essential_cut(
        normal_non_essential_total=normal_non_essential_total,
        anomaly_expense_total=anomaly_expense_total,
    )
    weekly_volatility = _compute_weekly_volatility(normal_expense_txs)
    stability_buffer = _compute_stability_buffer(
        normal_expense_total=normal_expense_total,
        weekly_volatility=weekly_volatility,
    )
    monthly_recovery_capacity = routine_net_total + recommended_non_essential_cut - stability_buffer

    estimated_recovery_months = _estimate_recovery_months(
        anomaly_expense_total=anomaly_expense_total,
        monthly_recovery_capacity=monthly_recovery_capacity,
    )

    return {
        "income_total": income_total,
        "expense_total": expense_total,
        "actual_net_total": actual_net_total,
        "anomaly_expense_total": anomaly_expense_total,
        "normal_expense_total": normal_expense_total,
        "normal_essential_expense_total": normal_essential_total,
        "normal_non_essential_expense_total": normal_non_essential_total,
        "routine_net_total": routine_net_total,
        "anomaly_count": len(anomaly_txs),
        "weekly_volatility": weekly_volatility,
        "stability_buffer": stability_buffer,
        "monthly_recovery_capacity": monthly_recovery_capacity.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        ),
        "estimated_recovery_months": estimated_recovery_months,
        "recommended_non_essential_cut": recommended_non_essential_cut,
        "summary": _build_summary(
            income_total=income_total,
            anomaly_expense_total=anomaly_expense_total,
            monthly_recovery_capacity=monthly_recovery_capacity,
            estimated_recovery_months=estimated_recovery_months,
        ),
        "actions": _build_actions(
            anomaly_expense_total=anomaly_expense_total,
            normal_non_essential_total=normal_non_essential_total,
            recommended_non_essential_cut=recommended_non_essential_cut,
            stability_buffer=stability_buffer,
            monthly_recovery_capacity=monthly_recovery_capacity,
            estimated_recovery_months=estimated_recovery_months,
        ),
        "anomaly_transactions": [
            {
                "id": tx.id,
                "external_tx_id": tx.external_tx_id,
                "occurred_at": tx.occurred_at,
                "amount": Decimal(tx.amount),
                "category": tx.category,
                "description": tx.description,
            }
            for tx in anomaly_txs
        ],
    }


def _sum_amounts(transactions) -> Decimal:
    return sum((Decimal(tx.amount) for tx in transactions), Decimal("0"))


def _is_non_essential(category: str | None) -> bool:
    if not category:
        return False
    return category.strip().lower() in NON_ESSENTIAL_CATEGORIES


def _recommended_non_essential_cut(
    *,
    normal_non_essential_total: Decimal,
    anomaly_expense_total: Decimal,
) -> Decimal:
    if normal_non_essential_total <= 0 or anomaly_expense_total <= 0:
        return Decimal("0.00")
    target = normal_non_essential_total * Decimal("0.15")
    return min(target, normal_non_essential_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _estimate_recovery_months(
    *,
    anomaly_expense_total: Decimal,
    monthly_recovery_capacity: Decimal,
) -> int | None:
    if anomaly_expense_total <= 0:
        return 0
    if monthly_recovery_capacity <= 0:
        return None
    months = (anomaly_expense_total / monthly_recovery_capacity).to_integral_value(
        rounding=ROUND_CEILING
    )
    return int(months)


def _build_summary(
    *,
    income_total: Decimal,
    anomaly_expense_total: Decimal,
    monthly_recovery_capacity: Decimal,
    estimated_recovery_months: int | None,
) -> str:
    if income_total == 0 and anomaly_expense_total == 0:
        return "No transaction data is available for anomaly impact analysis."
    if anomaly_expense_total == 0:
        return "No transaction-level anomaly expense was detected in this period."
    if monthly_recovery_capacity > 0 and estimated_recovery_months is not None:
        return (
            "Routine spending remains manageable after isolating anomaly expenses. "
            "Using adjusted monthly recovery capacity, the anomaly impact could be recovered "
            f"in about {estimated_recovery_months} month(s)."
        )
    return (
        "Anomaly expenses were detected, but routine spending does not leave a positive surplus. "
        "Reduce normal expenses or increase income before planning recovery."
    )


def _build_actions(
    *,
    anomaly_expense_total: Decimal,
    normal_non_essential_total: Decimal,
    recommended_non_essential_cut: Decimal,
    stability_buffer: Decimal,
    monthly_recovery_capacity: Decimal,
    estimated_recovery_months: int | None,
) -> list[str]:
    if anomaly_expense_total <= 0:
        return ["Continue monitoring transactions; no anomaly recovery action is required for this period."]

    actions = [
        "Treat anomaly expenses as exceptional shock items, not routine spending.",
        "Keep essential expenses separate from discretionary reductions.",
    ]
    if normal_non_essential_total > 0:
        actions.append(
            f"Target about {recommended_non_essential_cut} in discretionary reductions this month."
        )
    if stability_buffer > 0:
        actions.append(
            f"Keep about {stability_buffer} as a monthly stability buffer for normal spending variation."
        )
    if monthly_recovery_capacity > 0 and estimated_recovery_months is not None:
        actions.append(
            "Use adjusted recovery capacity "
            f"({monthly_recovery_capacity.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}) "
            f"to absorb the anomaly over about {estimated_recovery_months} month(s)."
        )
    else:
        actions.append("Create a positive routine surplus before assigning money to anomaly recovery.")
    return actions


def _compute_weekly_volatility(normal_expense_txs: list[Transaction]) -> float:
    weekly_totals: dict[tuple[int, int], Decimal] = {}
    for tx in normal_expense_txs:
        year, week, _ = tx.occurred_at.isocalendar()
        key = (year, week)
        if key not in weekly_totals:
            weekly_totals[key] = Decimal("0")
        weekly_totals[key] += Decimal(tx.amount)

    if len(weekly_totals) < 2:
        return 0.0

    weekly_values = [float(value) for _, value in sorted(weekly_totals.items())]
    weekly_mean = mean(weekly_values)
    if weekly_mean <= 0:
        return 0.0

    return float(pstdev(weekly_values) / weekly_mean)


def _compute_stability_buffer(
    *,
    normal_expense_total: Decimal,
    weekly_volatility: float,
) -> Decimal:
    if normal_expense_total <= 0 or weekly_volatility <= 0:
        return Decimal("0.00")

    buffer_rate = min(weekly_volatility * 0.10, 0.10)
    return (normal_expense_total * Decimal(str(buffer_rate))).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
