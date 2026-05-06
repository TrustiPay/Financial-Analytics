from decimal import Decimal
from statistics import mean, pstdev

from app.models import Transaction
from app.services.anomalies import detect_anomalies

# Keep discretionary categories broad enough for demo and advisory analysis.
NON_ESSENTIAL_CATEGORIES = {"entertainment", "shopping", "dining", "lifestyle", "travel"}


def compute_features(transactions: list[Transaction]) -> dict:
    income_txs = [tx for tx in transactions if tx.direction.lower() == "income"]
    expense_txs = [tx for tx in transactions if tx.direction.lower() == "expense"]

    income_total = sum((Decimal(tx.amount) for tx in income_txs), Decimal("0"))
    expense_total = sum((Decimal(tx.amount) for tx in expense_txs), Decimal("0"))
    net_total = income_total - expense_total

    savings_ratio = float(net_total / income_total) if income_total > 0 else None

    non_essential_expense_total = sum(
        (Decimal(tx.amount) for tx in expense_txs if _is_non_essential(tx.category)),
        Decimal("0"),
    )
    essential_expense_total = expense_total - non_essential_expense_total
    non_essential_ratio = (
        float(non_essential_expense_total / expense_total) if expense_total > 0 else None
    )

    weekly_totals = _weekly_expense_totals(expense_txs)
    weeks_count = len(weekly_totals)
    expense_tx_count = len(expense_txs)
    spending_frequency = float(expense_tx_count / weeks_count) if weeks_count > 0 else 0.0

    weekly_expense_mean: float | None = None
    weekly_expense_std: float | None = None
    spending_stability: float | None = None

    if weeks_count >= 2:
        weekly_values = [float(value) for _, value in sorted(weekly_totals.items())]
        weekly_expense_mean = mean(weekly_values)
        weekly_expense_std = pstdev(weekly_values)
        if weekly_expense_mean > 0:
            spending_stability = float(weekly_expense_std / weekly_expense_mean)

    anomalies = detect_anomalies(transactions)
    anomaly_count = len(anomalies)
    total_tx = len(transactions)
    anomaly_rate_per_100_tx = float((anomaly_count / total_tx) * 100) if total_tx > 0 else 0.0

    return {
        "income_total": income_total,
        "expense_total": expense_total,
        "net_total": net_total,
        "savings_ratio": savings_ratio,
        "non_essential_ratio": non_essential_ratio,
        "weekly_expense_mean": weekly_expense_mean,
        "weekly_expense_std": weekly_expense_std,
        "spending_stability": spending_stability,
        "expense_tx_count": expense_tx_count,
        "weeks_count": weeks_count,
        "spending_frequency": spending_frequency,
        "anomaly_count": anomaly_count,
        "anomaly_rate_per_100_tx": anomaly_rate_per_100_tx,
        "non_essential_expense_total": non_essential_expense_total,
        "essential_expense_total": essential_expense_total,
    }


def _is_non_essential(category: str | None) -> bool:
    if not category:
        return False
    normalized = category.strip().lower()
    return normalized in NON_ESSENTIAL_CATEGORIES


def _weekly_expense_totals(expense_txs: list[Transaction]) -> dict[tuple[int, int], Decimal]:
    weekly_totals: dict[tuple[int, int], Decimal] = {}
    for tx in expense_txs:
        year, week, _ = tx.occurred_at.isocalendar()
        key = (year, week)
        if key not in weekly_totals:
            weekly_totals[key] = Decimal("0")
        weekly_totals[key] += Decimal(tx.amount)
    return weekly_totals
