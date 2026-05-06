from datetime import datetime
import re
from typing import Any

import pandas as pd
import streamlit as st

_FEATURE_PREFIX_RE = re.compile(r"^(num|cat|remainder)__")
_WEEKDAY_NAMES = {
    "0": "Monday",
    "1": "Tuesday",
    "2": "Wednesday",
    "3": "Thursday",
    "4": "Friday",
    "5": "Saturday",
    "6": "Sunday",
}
_MONTH_NAMES = {
    "1": "January",
    "2": "February",
    "3": "March",
    "4": "April",
    "5": "May",
    "6": "June",
    "7": "July",
    "8": "August",
    "9": "September",
    "10": "October",
    "11": "November",
    "12": "December",
}
_FEATURE_LABELS = {
    "amount": "Transaction amount",
    "hour": "Time of day",
    "day_of_week": "Day of week",
    "month": "Month of year",
    "is_weekend": "Weekend timing",
    "is_night": "Late-night timing",
    "user_tx_count_prev": "Past transaction history",
    "user_avg_amount_prev": "Typical previous amount",
    "amount_to_user_avg_ratio": "Amount compared with usual spending",
    "category": "Spending category",
    "currency": "Currency",
    "user_ref": "Customer history pattern",
}
_FEATURE_EXPLANATIONS = {
    "amount": "Large transaction amounts tend to stand out more than smaller routine payments.",
    "hour": "The model checks whether this transaction happened at an unusual time of day.",
    "day_of_week": "Spending can look different depending on the day of the week.",
    "month": "Seasonal patterns can affect how unusual a transaction looks.",
    "is_weekend": "Weekend spending may behave differently from weekday spending.",
    "is_night": "Late-night transactions are often treated as less typical behavior.",
    "user_tx_count_prev": "The model uses prior history to understand how reliable the user's baseline is.",
    "user_avg_amount_prev": "This compares the payment against the user's normal historical amount.",
    "amount_to_user_avg_ratio": "This shows whether the amount is much higher or lower than the user's usual spend.",
    "category": "Some categories are more likely to look unusual than others.",
    "currency": "The payment currency is part of the model context.",
    "user_ref": "The score is influenced by the customer's own historical behavior pattern.",
}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _titleize_token(value: str) -> str:
    token = value.replace("_", " ").strip()
    if not token:
        return "Unknown"
    if len(token) == 3 and token.isalpha():
        return token.upper()
    return token.title()


def _humanize_feature_label(raw_feature: Any) -> str:
    feature = _FEATURE_PREFIX_RE.sub("", str(raw_feature or "")).strip()
    if not feature:
        return "Unknown factor"
    if feature in _FEATURE_LABELS:
        return _FEATURE_LABELS[feature]
    if feature.startswith("category_"):
        return f"Spending category: {_titleize_token(feature.removeprefix('category_'))}"
    if feature.startswith("currency_"):
        return f"Currency: {_titleize_token(feature.removeprefix('currency_'))}"
    if feature.startswith("user_ref_"):
        return "Customer history pattern"
    if feature.startswith("day_of_week_"):
        day_value = feature.removeprefix("day_of_week_")
        return f"Day of week: {_WEEKDAY_NAMES.get(day_value, day_value)}"
    if feature.startswith("month_"):
        month_value = feature.removeprefix("month_")
        return f"Month: {_MONTH_NAMES.get(month_value, month_value)}"
    return _titleize_token(feature)


def _feature_explanation(raw_feature: Any) -> str:
    feature = _FEATURE_PREFIX_RE.sub("", str(raw_feature or "")).strip()
    if not feature:
        return "The model marked this factor as relevant."
    if feature in _FEATURE_EXPLANATIONS:
        return _FEATURE_EXPLANATIONS[feature]
    if feature.startswith("category_"):
        category_value = _titleize_token(feature.removeprefix("category_"))
        return f"The {category_value} category affected how unusual this transaction looked."
    if feature.startswith("currency_"):
        currency_value = _titleize_token(feature.removeprefix("currency_"))
        return f"The {currency_value} currency contributed to the model's decision."
    if feature.startswith("user_ref_"):
        return _FEATURE_EXPLANATIONS["user_ref"]
    if feature.startswith("day_of_week_"):
        day_value = _WEEKDAY_NAMES.get(feature.removeprefix("day_of_week_"), "that day")
        return f"Transactions on {day_value} can behave differently from the user's normal weekly pattern."
    if feature.startswith("month_"):
        month_value = _MONTH_NAMES.get(feature.removeprefix("month_"), "that month")
        return f"The model used seasonal context from {month_value}."
    return "The model marked this factor as one of the strongest contributors for this prediction."


def format_risk_score(value: Any) -> str:
    score = _as_float(value)
    return f"{score:.1%}"


def format_risk_label(value: Any, is_high_risk: Any) -> str:
    level = "High risk" if bool(is_high_risk) else "Low risk"
    return f"{level} ({format_risk_score(value)})"


def format_timestamp(value: Any) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return str(value or "Unknown time")
    hour = parsed.strftime("%I").lstrip("0") or "0"
    return f"{parsed.strftime('%b %d, %Y')} {hour}:{parsed.strftime('%M %p')}"


def format_amount(value: Any, currency: Any = None) -> str:
    amount = _as_float(value)
    currency_code = str(currency or "").strip().upper()
    if currency_code:
        return f"{currency_code} {amount:,.2f}"
    return f"{amount:,.2f}"


def format_xai_prediction_title(prediction: dict[str, Any]) -> str:
    timestamp = format_timestamp(prediction.get("occurred_at"))
    category = prediction.get("category") or "Uncategorized"
    amount = format_amount(prediction.get("amount"), prediction.get("currency"))
    risk = format_risk_label(
        prediction.get("risk_score", 0.0),
        prediction.get("predicted_is_high_risk", False),
    )
    return f"{timestamp} | {category} | {amount} | {risk}"


def render_xai_factors(factors: list[dict[str, Any]] | None) -> None:
    if not factors:
        st.info("No xAI factors available for this prediction.")
        return

    rows = []
    for factor in factors:
        effect = str(factor.get("effect", "")).lower()
        if effect == "risk_up":
            effect_label = "Raises risk"
        elif effect == "risk_down":
            effect_label = "Lowers risk"
        else:
            effect_label = "Influences risk"

        rows.append(
            {
                "Factor": _humanize_feature_label(factor.get("feature")),
                "Effect": effect_label,
                "Impact Score": f"{_as_float(factor.get('contribution')):.4f}",
                "What It Means": _feature_explanation(factor.get("feature")),
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_xai_prediction_details(prediction: dict[str, Any]) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.write(f"**When:** {format_timestamp(prediction.get('occurred_at'))}")
    col2.write(f"**Amount:** {format_amount(prediction.get('amount'), prediction.get('currency'))}")
    col3.write(f"**Direction:** {str(prediction.get('direction', 'N/A')).title()}")
    col4.write(f"**Category:** {prediction.get('category') or 'Uncategorized'}")

    st.write(f"**Risk:** {format_risk_label(prediction.get('risk_score', 0.0), prediction.get('predicted_is_high_risk', False))}")
    st.markdown("**Top xAI Factors**")
    render_xai_factors(prediction.get("xai_factors", []))


def _format_trend_value(value: Any, unit: str) -> str:
    if value is None:
        return "N/A"
    numeric = _as_float(value)
    if unit == "ratio":
        return f"{numeric:.1%}"
    if unit == "rate":
        return f"{numeric:.1f}/100 tx"
    if unit == "frequency":
        return f"{numeric:.2f} tx/week"
    if unit == "currency":
        return f"{numeric:,.2f}"
    return f"{numeric:.2f}"


def _format_trend_delta(current_value: Any, baseline_value: Any, unit: str) -> str | None:
    if current_value is None or baseline_value is None:
        return None
    current_numeric = _as_float(current_value)
    baseline_numeric = _as_float(baseline_value)
    delta = current_numeric - baseline_numeric
    if unit == "ratio":
        return f"{delta * 100:+.1f} pts"
    if unit == "rate":
        return f"{delta:+.1f}/100 tx"
    if unit == "frequency":
        return f"{delta:+.2f} tx/week"
    if unit == "currency":
        return f"{delta:+,.2f}"
    return f"{delta:+.2f}"


def render_trend_summary(trends: dict[str, Any] | None) -> None:
    if not trends:
        st.info("Trend data unavailable.")
        return

    current_snapshot = trends.get("current_snapshot", {})
    baseline_snapshot = trends.get("baseline_snapshot", {}) or {}
    baseline_available = bool(trends.get("baseline_available", False))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Expense",
        _format_trend_value(current_snapshot.get("expense_total"), "currency"),
        _format_trend_delta(
            current_snapshot.get("expense_total"),
            baseline_snapshot.get("expense_total") if baseline_available else None,
            "currency",
        ),
    )
    col2.metric(
        "Savings Ratio",
        _format_trend_value(current_snapshot.get("savings_ratio"), "ratio"),
        _format_trend_delta(
            current_snapshot.get("savings_ratio"),
            baseline_snapshot.get("savings_ratio") if baseline_available else None,
            "ratio",
        ),
    )
    col3.metric(
        "Non-Essential Share",
        _format_trend_value(current_snapshot.get("non_essential_ratio"), "ratio"),
        _format_trend_delta(
            current_snapshot.get("non_essential_ratio"),
            baseline_snapshot.get("non_essential_ratio") if baseline_available else None,
            "ratio",
        ),
    )
    col4.metric(
        "Anomaly Rate",
        _format_trend_value(current_snapshot.get("anomaly_rate_per_100_tx"), "rate"),
        _format_trend_delta(
            current_snapshot.get("anomaly_rate_per_100_tx"),
            baseline_snapshot.get("anomaly_rate_per_100_tx") if baseline_available else None,
            "rate",
        ),
    )

    if trends.get("summary"):
        st.caption(str(trends.get("summary")))


def render_trend_comparison_table(trends: dict[str, Any] | None) -> None:
    if not trends:
        st.info("Trend comparison unavailable.")
        return

    current_snapshot = trends.get("current_snapshot", {})
    baseline_snapshot = trends.get("baseline_snapshot", {}) or {}
    baseline_available = bool(trends.get("baseline_available", False))

    metric_rows = [
        ("Expense", "expense_total", "currency"),
        ("Savings Ratio", "savings_ratio", "ratio"),
        ("Non-Essential Share", "non_essential_ratio", "ratio"),
        ("Spending Frequency", "spending_frequency", "frequency"),
        ("Spending Volatility", "spending_stability", "ratio"),
        ("Anomaly Rate", "anomaly_rate_per_100_tx", "rate"),
    ]

    rows = []
    for label, key, unit in metric_rows:
        current_value = current_snapshot.get(key)
        baseline_value = baseline_snapshot.get(key) if baseline_available else None
        rows.append(
            {
                "Metric": label,
                "Current": _format_trend_value(current_value, unit),
                "Baseline": _format_trend_value(baseline_value, unit) if baseline_available else "N/A",
                "Delta": _format_trend_delta(current_value, baseline_value, unit) or "N/A",
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_trend_series(trends: dict[str, Any] | None) -> None:
    if not trends:
        st.info("Trend series unavailable.")
        return

    series = trends.get("series", [])
    if not series:
        st.info("No trend series available for this selection.")
        return

    rows = []
    for item in series:
        rows.append(
            {
                "period": item.get("period"),
                "income": _as_float(item.get("income")),
                "expense": _as_float(item.get("expense")),
                "net": _as_float(item.get("net")),
                "expense_tx_count": int(item.get("expense_tx_count", 0)),
                "anomaly_count": int(item.get("anomaly_count", 0)),
            }
        )

    frame = pd.DataFrame(rows)
    st.markdown("**Expense Trend**")
    st.line_chart(frame.set_index("period")[["expense"]])
    st.markdown("**Activity Trend**")
    st.bar_chart(frame.set_index("period")[["expense_tx_count", "anomaly_count"]])
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render_drift_items(trends: dict[str, Any] | None) -> None:
    if not trends:
        st.info("Drift analysis unavailable.")
        return

    if not trends.get("baseline_available", False):
        st.info("Not enough prior history to compare against a baseline window.")
        return

    items = trends.get("drift_items", [])
    if not items:
        st.success("No material drift detected versus the prior period.")
        return

    for item in items:
        body = (
            f"**Current:** {_format_trend_value(item.get('current_value'), item.get('unit', 'number'))}\n\n"
            f"**Baseline:** {_format_trend_value(item.get('baseline_value'), item.get('unit', 'number'))}\n\n"
            f"**Direction:** {str(item.get('direction', 'N/A')).title()}\n\n"
            f"{item.get('summary', '')}"
        )

        title = f"{str(item.get('severity', 'low')).title()} Drift: {item.get('label', 'Metric')}"
        impact = str(item.get("impact", "neutral")).lower()
        if impact == "risk_up":
            if str(item.get("severity", "low")).lower() == "high":
                st.error(f"**{title}**\n\n{body}")
            elif str(item.get("severity", "low")).lower() == "medium":
                st.warning(f"**{title}**\n\n{body}")
            else:
                st.info(f"**{title}**\n\n{body}")
        else:
            st.success(f"**{title}**\n\n{body}")


def render_overview_metrics(
    *,
    summary: dict[str, Any] | None,
    fhs: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    anomalies: dict[str, Any] | None,
) -> None:
    income_total = _as_float(summary.get("income_total") if summary else 0)
    expense_total = _as_float(summary.get("expense_total") if summary else 0)
    net_total = _as_float(summary.get("net_total") if summary else 0)

    fhs_score = _as_float(fhs.get("score") if fhs else 0)
    interpretation = fhs.get("interpretation", "N/A") if fhs else "N/A"
    behavior_profile = profile.get("profile", "N/A") if profile else "N/A"
    anomaly_count = int(anomalies.get("anomaly_count", 0)) if anomalies else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Income", f"{income_total:,.2f}")
    col2.metric("Expense", f"{expense_total:,.2f}")
    col3.metric("Net", f"{net_total:,.2f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("FHS Score", f"{fhs_score:.1f}", delta=interpretation)
    col5.metric("Behavior Profile", behavior_profile)
    col6.metric("Anomalies", str(anomaly_count))


def render_summary_chart(summary: dict[str, Any] | None) -> None:
    if not summary:
        st.info("Summary data unavailable.")
        return

    series = summary.get("series", [])
    if not series:
        st.info("No summary series available for this selection.")
        return

    rows = []
    for point in series:
        rows.append(
            {
                "period": point.get("period"),
                "income": _as_float(point.get("income")),
                "expense": _as_float(point.get("expense")),
                "net": _as_float(point.get("net")),
            }
        )

    frame = pd.DataFrame(rows)
    st.line_chart(frame.set_index("period")[["income", "expense", "net"]])


def render_categories_chart(categories: dict[str, Any] | None) -> None:
    if not categories:
        st.info("Category data unavailable.")
        return

    items = categories.get("items", [])
    if not items:
        st.info("No expense categories found for this selection.")
        return

    rows = []
    for item in items:
        rows.append(
            {
                "category": item.get("category"),
                "expense_total": _as_float(item.get("expense_total")),
                "transaction_count": int(item.get("transaction_count", 0)),
            }
        )

    frame = pd.DataFrame(rows).sort_values(by="expense_total", ascending=False)
    st.bar_chart(frame.set_index("category")["expense_total"])
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render_anomalies_table(anomalies: dict[str, Any] | None) -> None:
    if not anomalies:
        st.info("Anomaly data unavailable.")
        return

    items = anomalies.get("items", [])
    if not items:
        st.success("No anomalies detected for this selection.")
        return

    rows = []
    for item in items:
        rows.append(
            {
                "type": item.get("type"),
                "occurred_at": item.get("occurred_at") or item.get("period"),
                "amount": _as_float(item.get("amount"), default=0.0),
                "score": _as_float(item.get("score"), default=0.0),
                "reason": item.get("reason"),
            }
        )

    frame = pd.DataFrame(rows)
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render_fhs_subscores(fhs: dict[str, Any] | None) -> None:
    if not fhs:
        st.info("FHS data unavailable.")
        return

    subscores = fhs.get("subscores", [])
    if not subscores:
        st.info("No subscore data available.")
        return

    rows = []
    for subscore in subscores:
        rows.append(
            {
                "component": subscore.get("name"),
                "score": _as_float(subscore.get("score")),
                "max_score": _as_float(subscore.get("max_score")),
                "status": subscore.get("status"),
                "reason": subscore.get("reason"),
            }
        )

    frame = pd.DataFrame(rows)
    st.bar_chart(frame.set_index("component")[["score", "max_score"]])
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render_profile_feature_vector(profile: dict[str, Any] | None) -> None:
    if not profile:
        st.info("Behavior profile data unavailable.")
        return

    vector = profile.get("feature_vector", {})
    if not vector:
        st.info("No profile feature vector available.")
        return

    frame = pd.DataFrame(
        [
            {"feature": "savings_ratio", "value": _as_float(vector.get("savings_ratio"))},
            {
                "feature": "non_essential_ratio",
                "value": _as_float(vector.get("non_essential_ratio")),
            },
            {
                "feature": "spending_stability",
                "value": _as_float(vector.get("spending_stability")),
            },
            {
                "feature": "anomaly_rate_per_100_tx",
                "value": _as_float(vector.get("anomaly_rate_per_100_tx")),
            },
        ]
    )
    st.bar_chart(frame.set_index("feature")["value"])
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render_recommendation_cards(recommendations: dict[str, Any] | None) -> None:
    if not recommendations:
        st.info("Recommendations are unavailable.")
        return

    items = recommendations.get("items", [])
    if not items:
        st.info("No recommendations for this selection.")
        return

    for item in sorted(items, key=lambda value: int(value.get("rank", 999))):
        title = f"#{item.get('rank', '?')} - {item.get('title', 'Recommendation')}"
        body = (
            f"**Component:** {item.get('component', 'general')}\n\n"
            f"**Message:** {item.get('message', '')}\n\n"
            f"**Reason:** {item.get('reason', '')}"
        )
        if item.get("estimated_impact"):
            body += f"\n\n**Estimated Impact:** {item.get('estimated_impact')}"

        priority = str(item.get("priority", "medium")).lower()
        if priority == "high":
            st.warning(f"**{title}**\n\n{body}")
        elif priority == "low":
            st.success(f"**{title}**\n\n{body}")
        else:
            st.info(f"**{title}**\n\n{body}")
