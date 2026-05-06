from datetime import datetime
from decimal import Decimal
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin

from app.models import Transaction

TRANSACTION_OUTLIER_THRESHOLD = 2.5
WEEKLY_SPIKE_THRESHOLD = 2.5
MAX_ANOMALIES = 50
ML_RISK_MIN_TRANSACTIONS = 20
ML_MAX_ITEMS = 25

_ML_MODEL: ClassifierMixin | None = None
_ML_THRESHOLD: float | None = None
_ML_LOAD_ATTEMPTED = False


def _resolve_model_path() -> Path:
    return Path(__file__).resolve().parents[2] / "synthetic_data" / "trustipay_anomaly_risk_model.joblib"


def _resolve_threshold_path() -> Path:
    return Path(__file__).resolve().parents[2] / "synthetic_data" / "trustipay_anomaly_risk_model.threshold.txt"


def _load_ml_model() -> tuple[ClassifierMixin | None, float]:
    global _ML_MODEL, _ML_THRESHOLD, _ML_LOAD_ATTEMPTED
    if _ML_LOAD_ATTEMPTED:
        return _ML_MODEL, (_ML_THRESHOLD if _ML_THRESHOLD is not None else 0.5)

    _ML_LOAD_ATTEMPTED = True
    threshold = 0.5

    model_path = _resolve_model_path()
    threshold_path = _resolve_threshold_path()
    if not model_path.exists():
        _ML_MODEL = None
        _ML_THRESHOLD = threshold
        return _ML_MODEL, threshold

    try:
        import joblib

        loaded_model = joblib.load(model_path)
        if not hasattr(loaded_model, "predict_proba"):
            _ML_MODEL = None
            _ML_THRESHOLD = threshold
            return _ML_MODEL, threshold
        _ML_MODEL = loaded_model
    except Exception:
        _ML_MODEL = None
        _ML_THRESHOLD = threshold
        return _ML_MODEL, threshold

    if threshold_path.exists():
        try:
            parsed = float(threshold_path.read_text(encoding="utf-8").strip())
            if 0.0 <= parsed <= 1.0:
                threshold = parsed
        except Exception:
            threshold = 0.5

    _ML_THRESHOLD = threshold
    return _ML_MODEL, threshold


def detect_anomalies(
    transactions: list[Transaction],
    transaction_threshold: float = TRANSACTION_OUTLIER_THRESHOLD,
    weekly_threshold: float = WEEKLY_SPIKE_THRESHOLD,
    max_items: int = MAX_ANOMALIES,
) -> list[dict]:
    outliers = detect_transaction_outliers(transactions, threshold=transaction_threshold)
    weekly_spikes = detect_weekly_spikes(transactions, threshold=weekly_threshold)
    ml_risks = detect_ml_risk_anomalies(transactions)
    combined = outliers + weekly_spikes + ml_risks

    combined.sort(key=_anomaly_sort_key, reverse=True)
    return combined[:max_items]


def detect_ml_risk_anomalies(
    transactions: list[Transaction],
    min_transactions: int = ML_RISK_MIN_TRANSACTIONS,
    max_items: int = ML_MAX_ITEMS,
) -> list[dict]:
    if len(transactions) < min_transactions:
        return []

    model, threshold = _load_ml_model()
    if model is None:
        return []

    tx_df = _build_ml_feature_frame(transactions)
    if tx_df.empty:
        return []

    try:
        risk_scores = model.predict_proba(tx_df)[:, 1]
    except Exception:
        return []

    scored_df = tx_df.assign(risk_score=risk_scores)
    risky = scored_df[scored_df["risk_score"] >= threshold].copy()
    if risky.empty:
        return []

    risky = risky.sort_values("risk_score", ascending=False).head(max_items)
    items: list[dict] = []
    for row in risky.itertuples(index=False):
        tx = row.tx
        score = float(row.risk_score)
        items.append(
            {
                "type": "ml_risk",
                "occurred_at": tx.occurred_at,
                "period": None,
                "transaction_id": tx.id,
                "external_tx_id": tx.external_tx_id,
                "amount": Decimal(tx.amount),
                "direction": tx.direction,
                "category": tx.category,
                "description": tx.description,
                "score": round(score, 4),
                "reason": (
                    "Transaction was flagged by the anomaly risk model "
                    f"(score={score:.2f}, threshold={threshold:.2f})."
                ),
            }
        )
    return items


def _build_ml_feature_frame(transactions: list[Transaction]) -> pd.DataFrame:
    ordered = sorted(
        transactions,
        key=lambda tx: (tx.user_ref, tx.occurred_at, tx.created_at, tx.id),
    )

    rows: list[dict] = []
    for tx in ordered:
        rows.append(
            {
                "tx": tx,
                "user_ref": tx.user_ref or "unknown-user",
                "occurred_at": tx.occurred_at,
                "amount": float(Decimal(tx.amount)),
                "category": tx.category or "Unknown",
                "currency": tx.currency or "Unknown",
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["hour"] = df["occurred_at"].dt.hour
    df["day_of_week"] = df["occurred_at"].dt.dayofweek
    df["month"] = df["occurred_at"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_night"] = ((df["hour"] <= 5) | (df["hour"] >= 22)).astype(int)

    df["user_tx_count_prev"] = df.groupby("user_ref").cumcount()
    df["user_avg_amount_prev"] = (
        df.groupby("user_ref")["amount"].transform(lambda s: s.shift(1).expanding().mean())
    )
    median_amount = float(df["amount"].median()) if not df["amount"].empty else 0.0
    df["user_avg_amount_prev"] = df["user_avg_amount_prev"].fillna(median_amount)
    df["amount_to_user_avg_ratio"] = (
        df["amount"] / df["user_avg_amount_prev"]
    ).replace([np.inf, -np.inf], np.nan).fillna(1.0)

    feature_cols = [
        "user_ref",
        "category",
        "currency",
        "amount",
        "hour",
        "day_of_week",
        "month",
        "is_weekend",
        "is_night",
        "user_tx_count_prev",
        "user_avg_amount_prev",
        "amount_to_user_avg_ratio",
    ]
    return df[["tx", *feature_cols]]


def detect_transaction_outliers(
    transactions: list[Transaction],
    threshold: float = TRANSACTION_OUTLIER_THRESHOLD,
) -> list[dict]:
    expenses = [tx for tx in transactions if tx.direction.lower() == "expense"]
    if len(expenses) < 2:
        return []

    amounts = [float(Decimal(tx.amount)) for tx in expenses]
    std = pstdev(amounts)
    if std == 0:
        return []

    avg = mean(amounts)
    items: list[dict] = []
    for tx in expenses:
        tx_amount = float(Decimal(tx.amount))
        z = (tx_amount - avg) / std
        if z >= threshold:
            score = round(abs(z), 4)
            items.append(
                {
                    "type": "transaction_outlier",
                    "occurred_at": tx.occurred_at,
                    "period": None,
                    "transaction_id": tx.id,
                    "external_tx_id": tx.external_tx_id,
                    "amount": Decimal(tx.amount),
                    "direction": tx.direction,
                    "category": tx.category,
                    "description": tx.description,
                    "score": score,
                    "reason": (
                        "Transaction amount is unusually high "
                        f"(z={score:.2f}) compared to your typical expenses in this period."
                    ),
                }
            )
    return items


def detect_weekly_spikes(
    transactions: list[Transaction],
    threshold: float = WEEKLY_SPIKE_THRESHOLD,
) -> list[dict]:
    weekly_totals: dict[tuple[int, int], Decimal] = {}
    for tx in transactions:
        if tx.direction.lower() != "expense":
            continue
        iso_year, iso_week, _ = tx.occurred_at.isocalendar()
        week_key = (iso_year, iso_week)
        if week_key not in weekly_totals:
            weekly_totals[week_key] = Decimal("0")
        weekly_totals[week_key] += Decimal(tx.amount)

    if len(weekly_totals) < 2:
        return []

    totals = [float(total) for total in weekly_totals.values()]
    std = pstdev(totals)
    if std == 0:
        return []

    avg = mean(totals)
    items: list[dict] = []
    for (iso_year, iso_week), total in weekly_totals.items():
        z = (float(total) - avg) / std
        if z >= threshold:
            score = round(abs(z), 4)
            period = f"{iso_year}-W{iso_week:02d}"
            week_start = datetime.fromisocalendar(iso_year, iso_week, 1)
            items.append(
                {
                    "type": "weekly_spike",
                    "occurred_at": week_start,
                    "period": period,
                    "transaction_id": None,
                    "external_tx_id": None,
                    "amount": total,
                    "direction": "expense",
                    "category": None,
                    "description": None,
                    "score": score,
                    "reason": (
                        "Weekly spending total is unusually high "
                        f"(z={score:.2f}) compared to other weeks in the selected period."
                    ),
                }
            )
    return items


def _anomaly_sort_key(item: dict) -> tuple[float, datetime, str]:
    occurred_at = item.get("occurred_at")
    if not isinstance(occurred_at, datetime):
        occurred_at = _period_to_datetime(item.get("period"))
    tie_breaker = str(item.get("transaction_id") or item.get("period") or "")
    return (float(item.get("score", 0.0)), occurred_at, tie_breaker)


def _period_to_datetime(period: str | None) -> datetime:
    if not period:
        return datetime.min
    try:
        year_str, week_part = period.split("-W")
        return datetime.fromisocalendar(int(year_str), int(week_part), 1)
    except Exception:
        return datetime.min


def predict_transaction_risks(
    *,
    user_ref: str,
    history_transactions: list[Transaction],
    candidate_transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    model, threshold = _load_ml_model()
    if model is None:
        return {
            "model_available": False,
            "model_name": None,
            "threshold": threshold,
            "predictions": [],
        }

    feature_df, metadata = _build_prediction_feature_frame(
        user_ref=user_ref,
        history_transactions=history_transactions,
        candidate_transactions=candidate_transactions,
    )
    if feature_df.empty:
        return {
            "model_available": True,
            "model_name": type(model).__name__,
            "threshold": threshold,
            "predictions": [],
        }

    try:
        risk_scores = model.predict_proba(feature_df)[:, 1]
    except Exception:
        return {
            "model_available": False,
            "model_name": None,
            "threshold": threshold,
            "predictions": [],
        }

    transformed, feature_names, importances = _extract_model_xai_parts(model, feature_df)

    predictions: list[dict[str, Any]] = []
    for idx, meta in enumerate(metadata):
        score = float(risk_scores[idx])
        xai_factors = _build_xai_factors(
            transformed=transformed,
            feature_names=feature_names,
            importances=importances,
            row_index=idx,
            fallback_meta=meta,
        )
        predictions.append(
            {
                "index": int(meta["input_index"]),
                "occurred_at": meta["occurred_at"],
                "amount": Decimal(str(meta["amount"])).quantize(Decimal("0.01")),
                "direction": meta["direction"],
                "category": meta.get("category"),
                "risk_score": round(score, 4),
                "predicted_is_high_risk": score >= threshold,
                "xai_factors": xai_factors,
            }
        )

    predictions.sort(key=lambda p: p["index"])
    return {
        "model_available": True,
        "model_name": type(model).__name__,
        "threshold": threshold,
        "predictions": predictions,
    }


def _normalize_direction_for_prediction(direction: str | None) -> str:
    if not direction:
        return "expense"
    normalized = direction.strip().lower()
    mapping = {
        "debit": "expense",
        "credit": "income",
        "expense": "expense",
        "income": "income",
    }
    return mapping.get(normalized, "expense")


def _build_prediction_feature_frame(
    *,
    user_ref: str,
    history_transactions: list[Transaction],
    candidate_transactions: list[dict[str, Any]],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []

    for tx in history_transactions:
        rows.append(
            {
                "is_candidate": False,
                "input_index": None,
                "user_ref": tx.user_ref or user_ref,
                "occurred_at": tx.occurred_at,
                "amount": float(Decimal(tx.amount)),
                "direction": _normalize_direction_for_prediction(tx.direction),
                "category": tx.category or "Unknown",
                "currency": tx.currency or "Unknown",
            }
        )

    for idx, item in enumerate(candidate_transactions):
        rows.append(
            {
                "is_candidate": True,
                "input_index": idx,
                "user_ref": user_ref,
                "occurred_at": item["occurred_at"],
                "amount": float(Decimal(item["amount"])),
                "direction": _normalize_direction_for_prediction(item.get("direction")),
                "category": item.get("category") or "Unknown",
                "currency": item.get("currency") or "Unknown",
            }
        )

    if not rows:
        return pd.DataFrame(), []

    df = pd.DataFrame(rows)
    df = df.sort_values(["user_ref", "occurred_at", "is_candidate"]).reset_index(drop=True)

    df["hour"] = df["occurred_at"].dt.hour
    df["day_of_week"] = df["occurred_at"].dt.dayofweek
    df["month"] = df["occurred_at"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_night"] = ((df["hour"] <= 5) | (df["hour"] >= 22)).astype(int)

    df["user_tx_count_prev"] = df.groupby("user_ref").cumcount()
    df["user_avg_amount_prev"] = (
        df.groupby("user_ref")["amount"].transform(lambda s: s.shift(1).expanding().mean())
    )
    median_amount = float(df["amount"].median()) if not df["amount"].empty else 1.0
    df["user_avg_amount_prev"] = df["user_avg_amount_prev"].fillna(median_amount)
    df["amount_to_user_avg_ratio"] = (
        df["amount"] / df["user_avg_amount_prev"]
    ).replace([np.inf, -np.inf], np.nan).fillna(1.0)

    feature_cols = [
        "user_ref",
        "category",
        "currency",
        "amount",
        "hour",
        "day_of_week",
        "month",
        "is_weekend",
        "is_night",
        "user_tx_count_prev",
        "user_avg_amount_prev",
        "amount_to_user_avg_ratio",
    ]

    candidate_df = df[df["is_candidate"]].copy()
    metadata = [
        {
            "input_index": int(row["input_index"]),
            "occurred_at": row["occurred_at"],
            "amount": row["amount"],
            "direction": row["direction"],
            "category": None if row["category"] == "Unknown" else row["category"],
            "is_night": int(row["is_night"]),
            "amount_to_user_avg_ratio": float(row["amount_to_user_avg_ratio"]),
        }
        for _, row in candidate_df.iterrows()
    ]
    return candidate_df[feature_cols], metadata


def _extract_model_xai_parts(
    model: ClassifierMixin,
    feature_df: pd.DataFrame,
) -> tuple[Any, list[str], np.ndarray | None]:
    transformed = None
    feature_names: list[str] = []
    importances: np.ndarray | None = None

    try:
        if hasattr(model, "named_steps") and "preprocess" in model.named_steps and "clf" in model.named_steps:
            preprocess = model.named_steps["preprocess"]
            clf = model.named_steps["clf"]
            transformed = preprocess.transform(feature_df)
            feature_names = list(preprocess.get_feature_names_out())
            if hasattr(clf, "feature_importances_"):
                importances = np.asarray(clf.feature_importances_, dtype=float)
        elif hasattr(model, "feature_importances_"):
            importances = np.asarray(model.feature_importances_, dtype=float)
    except Exception:
        transformed = None
        feature_names = []
        importances = None

    return transformed, feature_names, importances


def _build_xai_factors(
    *,
    transformed: Any,
    feature_names: list[str],
    importances: np.ndarray | None,
    row_index: int,
    fallback_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    if transformed is not None and importances is not None and feature_names:
        try:
            row = transformed[row_index]
            if hasattr(row, "toarray"):
                row_values = np.asarray(row.toarray()).ravel()
            else:
                row_values = np.asarray(row).ravel()

            size = min(len(row_values), len(importances), len(feature_names))
            if size > 0:
                scores = np.abs(row_values[:size]) * np.abs(importances[:size])
                top_idx = np.argsort(scores)[::-1]
                factors: list[dict[str, Any]] = []
                for feature_idx in top_idx:
                    if len(factors) >= 3:
                        break
                    contribution = float(scores[feature_idx])
                    if contribution <= 0:
                        continue
                    factors.append(
                        {
                            "feature": feature_names[feature_idx],
                            "contribution": round(contribution, 4),
                            "effect": "risk_up",
                        }
                    )
                if factors:
                    return factors
        except Exception:
            pass

    ratio = float(fallback_meta.get("amount_to_user_avg_ratio", 1.0))
    is_night = int(fallback_meta.get("is_night", 0))
    category = (fallback_meta.get("category") or "").strip().lower()
    risky_categories = {"travel", "shopping", "entertainment", "debt"}

    fallback_factors: list[dict[str, Any]] = [
        {
            "feature": "num__amount_to_user_avg_ratio",
            "contribution": round(min(max((ratio - 1.0) / 2.5, 0.0), 1.0), 4),
            "effect": "risk_up" if ratio >= 1.0 else "risk_down",
        }
    ]

    if is_night == 1:
        fallback_factors.append(
            {
                "feature": "num__is_night",
                "contribution": 0.25,
                "effect": "risk_up",
            }
        )

    if category in risky_categories:
        fallback_factors.append(
            {
                "feature": "cat__category",
                "contribution": 0.2,
                "effect": "risk_up",
            }
        )

    return fallback_factors[:3]
