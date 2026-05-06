from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.models import Transaction


def fetch_transactions(
    db: Session,
    user_ref: str,
    from_dt: datetime,
    to_dt: datetime,
) -> list[Transaction]:
    return (
        db.query(Transaction)
        .filter(
            Transaction.user_ref == user_ref,
            Transaction.occurred_at >= from_dt,
            Transaction.occurred_at <= to_dt,
        )
        .order_by(Transaction.occurred_at.asc(), Transaction.created_at.asc())
        .all()
    )


def compute_summary(
    transactions: list[Transaction],
    group_by: Literal["day", "week", "month"],
) -> tuple[Decimal, Decimal, list[dict[str, Decimal | str]]]:
    buckets: dict[str, dict[str, Decimal]] = {}
    bucket_sort_keys: dict[str, tuple[int, ...]] = {}
    income_total = Decimal("0")
    expense_total = Decimal("0")

    for tx in transactions:
        amount = Decimal(tx.amount)
        direction = tx.direction.lower()

        if direction == "income":
            income_total += amount
        elif direction == "expense":
            expense_total += amount
        else:
            continue

        period, sort_key = _bucket_for(tx.occurred_at, group_by)
        if period not in buckets:
            buckets[period] = {"income": Decimal("0"), "expense": Decimal("0")}
            bucket_sort_keys[period] = sort_key

        buckets[period][direction] += amount

    series: list[dict[str, Decimal | str]] = []
    for period in sorted(buckets.keys(), key=lambda k: bucket_sort_keys[k]):
        bucket_income = buckets[period]["income"]
        bucket_expense = buckets[period]["expense"]
        series.append(
            {
                "period": period,
                "income": bucket_income,
                "expense": bucket_expense,
                "net": bucket_income - bucket_expense,
            }
        )

    return income_total, expense_total, series


def compute_category_breakdown(
    transactions: list[Transaction],
) -> tuple[list[dict[str, Decimal | int | str]], Decimal]:
    category_map: dict[str, dict[str, Decimal | int]] = {}
    total_expense = Decimal("0")

    for tx in transactions:
        if tx.direction.lower() != "expense":
            continue

        amount = Decimal(tx.amount)
        category_name = tx.category.strip() if tx.category and tx.category.strip() else "Uncategorized"

        if category_name not in category_map:
            category_map[category_name] = {
                "expense_total": Decimal("0"),
                "transaction_count": 0,
            }

        category_map[category_name]["expense_total"] += amount
        category_map[category_name]["transaction_count"] += 1
        total_expense += amount

    items = [
        {
            "category": category,
            "expense_total": data["expense_total"],
            "transaction_count": int(data["transaction_count"]),
        }
        for category, data in category_map.items()
    ]

    items.sort(
        key=lambda item: (
            -Decimal(item["expense_total"]),
            str(item["category"]).lower(),
        )
    )

    return items, total_expense


def _bucket_for(
    occurred_at: datetime,
    group_by: Literal["day", "week", "month"],
) -> tuple[str, tuple[int, ...]]:
    if group_by == "day":
        date_value = occurred_at.date()
        return date_value.isoformat(), (date_value.year, date_value.month, date_value.day)
    if group_by == "month":
        return occurred_at.strftime("%Y-%m"), (occurred_at.year, occurred_at.month)

    iso_year, iso_week, _ = occurred_at.isocalendar()
    return f"{iso_year}-W{iso_week:02d}", (iso_year, iso_week)
