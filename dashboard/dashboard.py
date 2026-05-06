import calendar
from datetime import date, datetime, time, timedelta
import re
from typing import Any
import uuid

import streamlit as st

import api_client
from components import (
    format_risk_score,
    format_xai_prediction_title,
    render_drift_items,
    render_anomalies_table,
    render_categories_chart,
    render_fhs_subscores,
    render_overview_metrics,
    render_profile_feature_vector,
    render_recommendation_cards,
    render_summary_chart,
    render_trend_comparison_table,
    render_trend_series,
    render_trend_summary,
    render_xai_factors,
    render_xai_prediction_details,
)

MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


@st.cache_data(ttl=30)
def load_health() -> dict[str, Any]:
    return api_client.get_health()


@st.cache_data(ttl=30)
def load_users() -> dict[str, Any]:
    return api_client.get_users()


@st.cache_data(ttl=30)
def load_transactions(
    user_ref: str,
    from_date: date | None,
    to_date: date | None,
    limit: int,
    offset: int,
    direction: str | None,
    category: str | None,
) -> dict[str, Any]:
    return api_client.get_transactions(
        user_ref=user_ref,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
        direction=direction,
        category=category,
    )


@st.cache_data(ttl=30)
def load_summary(user_ref: str, from_date: date | None, to_date: date | None, group_by: str) -> dict[str, Any]:
    return api_client.get_summary(
        user_ref=user_ref,
        from_date=from_date,
        to_date=to_date,
        group_by=group_by,
    )


@st.cache_data(ttl=30)
def load_categories(user_ref: str, from_date: date | None, to_date: date | None) -> dict[str, Any]:
    return api_client.get_categories(user_ref=user_ref, from_date=from_date, to_date=to_date)


@st.cache_data(ttl=30)
def load_anomalies(user_ref: str, from_date: date | None, to_date: date | None) -> dict[str, Any]:
    return api_client.get_anomalies(user_ref=user_ref, from_date=from_date, to_date=to_date)


@st.cache_data(ttl=30)
def load_anomaly_impact(
    user_ref: str,
    month: str | None,
    from_date: date | None,
    to_date: date | None,
) -> dict[str, Any]:
    return api_client.get_anomaly_impact(
        user_ref=user_ref,
        month=month,
        from_date=from_date,
        to_date=to_date,
    )


@st.cache_data(ttl=30)
def load_features(
    user_ref: str,
    month: str | None,
    from_date: date | None,
    to_date: date | None,
) -> dict[str, Any]:
    return api_client.get_features(user_ref=user_ref, month=month, from_date=from_date, to_date=to_date)


@st.cache_data(ttl=30)
def load_trends(
    user_ref: str,
    month: str | None,
    from_date: date | None,
    to_date: date | None,
    group_by: str,
) -> dict[str, Any]:
    return api_client.get_trends(
        user_ref=user_ref,
        month=month,
        from_date=from_date,
        to_date=to_date,
        group_by=group_by,
    )


@st.cache_data(ttl=30)
def load_fhs(user_ref: str, month: str | None, from_date: date | None, to_date: date | None) -> dict[str, Any]:
    return api_client.get_fhs(user_ref=user_ref, month=month, from_date=from_date, to_date=to_date)


@st.cache_data(ttl=30)
def load_behavior_profile(
    user_ref: str,
    month: str | None,
    from_date: date | None,
    to_date: date | None,
) -> dict[str, Any]:
    return api_client.get_behavior_profile(
        user_ref=user_ref,
        month=month,
        from_date=from_date,
        to_date=to_date,
    )


@st.cache_data(ttl=30)
def load_recommendations(
    user_ref: str,
    month: str | None,
    from_date: date | None,
    to_date: date | None,
) -> dict[str, Any]:
    return api_client.get_recommendations(
        user_ref=user_ref,
        month=month,
        from_date=from_date,
        to_date=to_date,
    )


def safe_call(label: str, fn, *args, **kwargs) -> dict[str, Any] | None:
    try:
        return fn(*args, **kwargs)
    except RuntimeError as exc:
        st.error(f"{label}: {exc}")
        return None


def resolve_date_range(value: Any) -> tuple[date | None, date | None]:
    if isinstance(value, tuple) and len(value) == 2:
        return value[0], value[1]
    if isinstance(value, list) and len(value) == 2:
        return value[0], value[1]
    return None, None


def render_anomaly_impact(impact: dict[str, Any] | None) -> None:
    if not impact:
        st.info("Anomaly impact is unavailable for this selection.")
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("Actual Net", f"{float(impact.get('actual_net_total', 0)):.2f}")
    metric_cols[1].metric("Routine Net", f"{float(impact.get('routine_net_total', 0)):.2f}")
    metric_cols[2].metric("Anomaly Expense", f"{float(impact.get('anomaly_expense_total', 0)):.2f}")
    recovery_months = impact.get("estimated_recovery_months")
    metric_cols[3].metric("Estimated Recovery", "N/A" if recovery_months is None else f"{recovery_months} mo")

    st.caption(str(impact.get("summary", "")))
    st.caption(
        "Formula: ceil(anomaly expense / monthly recovery capacity), where monthly recovery capacity = "
        "routine net + recommended non-essential cut - stability buffer."
    )

    breakdown = {
        "Metric": [
            "Income",
            "All Expenses",
            "Normal Expenses",
            "Normal Essential",
            "Normal Non-Essential",
            "Recommended Non-Essential Cut",
            "Stability Buffer",
            "Monthly Recovery Capacity",
            "Weekly Volatility",
        ],
        "Amount": [
            impact.get("income_total", "0.00"),
            impact.get("expense_total", "0.00"),
            impact.get("normal_expense_total", "0.00"),
            impact.get("normal_essential_expense_total", "0.00"),
            impact.get("normal_non_essential_expense_total", "0.00"),
            impact.get("recommended_non_essential_cut", "0.00"),
            impact.get("stability_buffer", "0.00"),
            impact.get("monthly_recovery_capacity", "0.00"),
            f"{float(impact.get('weekly_volatility', 0.0)):.4f}",
        ],
    }
    st.table(breakdown)

    actions = impact.get("actions", [])
    if actions:
        st.markdown("##### Recovery Actions")
        for action in actions:
            st.write(f"- {action}")

    anomaly_transactions = impact.get("anomaly_transactions", [])
    if anomaly_transactions:
        st.markdown("##### Isolated Anomaly Transactions")
        st.dataframe(anomaly_transactions, use_container_width=True, hide_index=True)


def shift_month(value: date, month_offset: int) -> date:
    total_months = (value.year * 12 + value.month - 1) + month_offset
    year = total_months // 12
    month = total_months % 12 + 1
    return date(year, month, 1)


def build_history_record(
    *,
    user_ref: str,
    occurred_at: datetime,
    amount: float,
    direction: str,
    category: str | None,
    description: str | None,
    currency: str | None,
    external_tx_id: str | None = None,
) -> dict[str, Any]:
    return {
        "external_tx_id": external_tx_id or f"{user_ref}-{uuid.uuid4().hex[:12]}",
        "user_ref": user_ref,
        "occurred_at": occurred_at.isoformat(),
        "amount": float(amount),
        "direction": direction,
        "category": category,
        "description": description,
        "currency": currency,
    }


def build_starter_history(
    *,
    user_ref: str,
    anchor_month: date,
    monthly_income: float,
    currency: str,
) -> list[dict[str, Any]]:
    month_configs = [
        {
            "income": monthly_income * 0.98,
            "utilities": 7800.0,
            "transport": 4800.0,
            "food": 14500.0,
            "shopping": 9000.0,
            "entertainment": 5000.0,
        },
        {
            "income": monthly_income,
            "utilities": 8100.0,
            "transport": 5200.0,
            "food": 15500.0,
            "shopping": 13000.0,
            "entertainment": 7000.0,
        },
        {
            "income": monthly_income * 1.02,
            "utilities": 8300.0,
            "transport": 5600.0,
            "food": 16800.0,
            "shopping": 17000.0,
            "entertainment": 8500.0,
        },
    ]

    records: list[dict[str, Any]] = []
    for month_offset, config in zip((-2, -1, 0), month_configs):
        month_start = shift_month(anchor_month, month_offset)
        year = month_start.year
        month = month_start.month
        last_day = calendar.monthrange(year, month)[1]

        def month_dt(day: int, hour: int, minute: int) -> datetime:
            safe_day = min(day, last_day)
            return datetime(year, month, safe_day, hour, minute)

        month_prefix = f"{year}{month:02d}"
        records.extend(
            [
                build_history_record(
                    user_ref=user_ref,
                    occurred_at=month_dt(1, 8, 0),
                    amount=config["income"],
                    direction="income",
                    category="Salary",
                    description="Monthly salary",
                    currency=currency,
                    external_tx_id=f"{user_ref}-{month_prefix}-salary",
                ),
                build_history_record(
                    user_ref=user_ref,
                    occurred_at=month_dt(4, 9, 0),
                    amount=config["utilities"],
                    direction="expense",
                    category="Utilities",
                    description="Electricity and water",
                    currency=currency,
                    external_tx_id=f"{user_ref}-{month_prefix}-utilities",
                ),
                build_history_record(
                    user_ref=user_ref,
                    occurred_at=month_dt(7, 8, 30),
                    amount=config["transport"],
                    direction="expense",
                    category="Transport",
                    description="Fuel and travel",
                    currency=currency,
                    external_tx_id=f"{user_ref}-{month_prefix}-transport",
                ),
                build_history_record(
                    user_ref=user_ref,
                    occurred_at=month_dt(12, 13, 0),
                    amount=config["food"],
                    direction="expense",
                    category="Food",
                    description="Groceries",
                    currency=currency,
                    external_tx_id=f"{user_ref}-{month_prefix}-food",
                ),
                build_history_record(
                    user_ref=user_ref,
                    occurred_at=month_dt(18, 18, 30),
                    amount=config["shopping"],
                    direction="expense",
                    category="Shopping",
                    description="Household and shopping",
                    currency=currency,
                    external_tx_id=f"{user_ref}-{month_prefix}-shopping",
                ),
                build_history_record(
                    user_ref=user_ref,
                    occurred_at=month_dt(24, 20, 15),
                    amount=config["entertainment"],
                    direction="expense",
                    category="Entertainment",
                    description="Weekend activities",
                    currency=currency,
                    external_tx_id=f"{user_ref}-{month_prefix}-entertainment",
                ),
            ]
        )

    return records


def main() -> None:
    st.set_page_config(page_title="TrustiPay Analytics Dashboard", layout="wide")

    st.title("TrustiPay Analytics Dashboard")
    st.caption("Dashboard data is fetched from FastAPI endpoints only.")

    with st.sidebar:
        st.header("Controls")
        st.caption(f"API Base URL: {api_client.API_BASE_URL}")

        health = safe_call("Health check failed", load_health)
        if health and health.get("status") == "ok":
            st.success("Backend is online")
        else:
            st.error("Backend is unavailable or degraded")

        users_payload = safe_call("Failed to fetch users", load_users)
        user_items = users_payload.get("items", []) if users_payload else []
        user_refs = sorted({item.get("user_ref", "") for item in user_items if item.get("user_ref")})

        selected_user = None
        if not user_refs:
            st.warning("No users available yet. Use the Add Customer tab to create one.")
        else:
            default_index = user_refs.index("demo-user-001") if "demo-user-001" in user_refs else 0
            selected_user = st.selectbox("User", options=user_refs, index=default_index)

        default_month = date.today().strftime("%Y-%m")
        month_value = st.text_input("Month (YYYY-MM)", value=default_month).strip()
        month_is_valid = bool(MONTH_PATTERN.fullmatch(month_value))
        if not month_is_valid:
            st.warning("Invalid month format. Expected YYYY-MM.")

        default_from = date.today() - timedelta(days=30)
        default_to = date.today()
        date_range = st.date_input("Date range", value=(default_from, default_to))
        from_date, to_date = resolve_date_range(date_range)

        group_by = st.selectbox("Summary groupBy", options=["day", "week", "month"], index=2)
        if st.button("Refresh"):
            st.cache_data.clear()
            st.rerun()

    effective_month = month_value if month_is_valid else None

    summary = None
    categories = None
    anomalies = None
    anomaly_impact = None
    features = None
    trends = None
    fhs = None
    profile = None
    recommendations = None
    if selected_user:
        summary = safe_call("Summary failed", load_summary, selected_user, from_date, to_date, group_by)
        categories = safe_call("Categories failed", load_categories, selected_user, from_date, to_date)
        anomalies = safe_call("Anomalies failed", load_anomalies, selected_user, from_date, to_date)
        anomaly_impact = safe_call(
            "Anomaly impact failed",
            load_anomaly_impact,
            selected_user,
            effective_month,
            from_date,
            to_date,
        )
        features = safe_call("Features failed", load_features, selected_user, effective_month, from_date, to_date)
        trends = safe_call("Trend report failed", load_trends, selected_user, None, from_date, to_date, group_by)
        fhs = safe_call("FHS failed", load_fhs, selected_user, effective_month, from_date, to_date)
        profile = safe_call(
            "Behavior profile failed",
            load_behavior_profile,
            selected_user,
            effective_month,
            from_date,
            to_date,
        )
        recommendations = safe_call(
            "Recommendations failed",
            load_recommendations,
            selected_user,
            effective_month,
            from_date,
            to_date,
        )

    tab_overview, tab_transactions, tab_reports, tab_fhs, tab_profile, tab_recommendations, tab_predict, tab_batch_predict, tab_add_customer = st.tabs(
        ["Overview", "Transactions", "Reports", "FHS", "Profile", "Recommendations", "Predict", "Batch Predict", "Add Customer"]
    )

    with tab_overview:
        st.subheader("Overview")
        if not selected_user:
            st.info("No user selected. Create a customer in the Add Customer tab.")
        else:
            st.write(f"**User:** `{selected_user}`")
            if effective_month:
                st.write(f"**Month:** `{effective_month}`")
            if from_date and to_date:
                st.write(f"**Date Range:** `{from_date.isoformat()} -> {to_date.isoformat()}`")

            render_overview_metrics(summary=summary, fhs=fhs, profile=profile, anomalies=anomalies)

    with tab_transactions:
        st.subheader("Transactions")
        if not selected_user:
            st.info("No user selected. Create a customer in the Add Customer tab.")
        else:
            col_filter1, col_filter2, col_filter3 = st.columns(3)
            direction_filter = col_filter1.selectbox("Direction", options=["all", "income", "expense"], index=0)
            category_filter = col_filter2.text_input("Category (exact)", value="").strip() or None
            tx_limit = col_filter3.slider("Limit", min_value=10, max_value=500, value=100, step=10)

            tx_response = safe_call(
                "Transactions fetch failed",
                load_transactions,
                selected_user,
                from_date,
                to_date,
                tx_limit,
                0,
                None if direction_filter == "all" else direction_filter,
                category_filter,
            )

            items = tx_response.get("items", []) if tx_response else []
            if not items:
                st.info("No transactions found for this selection.")
            else:
                st.dataframe(items, use_container_width=True, hide_index=True)

    with tab_reports:
        st.subheader("Summary")
        render_summary_chart(summary)

        st.subheader("Trend + Drift Detection")
        render_trend_summary(trends)
        st.markdown("#### Current Vs Baseline")
        render_trend_comparison_table(trends)
        st.markdown("#### Behavior Trend")
        render_trend_series(trends)

        st.markdown("#### Drift Signals")
        render_drift_items(trends)

        st.subheader("Category Breakdown")
        render_categories_chart(categories)

        st.subheader("Anomalies")
        render_anomalies_table(anomalies)

        st.subheader("Anomaly Impact + Recovery")
        render_anomaly_impact(anomaly_impact)

        st.subheader("xAI (Recent Transactions)")
        st.caption("Automatic xAI preview for the selected customer based on recent expense transactions.")
        if not selected_user:
            st.info("No user selected. Create a customer in the Add Customer tab.")
        else:
            recent_tx_response = safe_call(
                "Recent transactions fetch failed",
                load_transactions,
                selected_user,
                from_date,
                to_date,
                5,
                0,
                "expense",
                None,
            )

            recent_items = recent_tx_response.get("items", []) if recent_tx_response else []
            if not recent_items:
                st.info("No recent expense transactions to explain.")
            else:
                recent_payload = [
                    {
                        "occurred_at": tx.get("occurred_at"),
                        "amount": float(tx.get("amount", 0) or 0),
                        "direction": tx.get("direction", "expense"),
                        "category": tx.get("category"),
                        "description": tx.get("description"),
                        "currency": tx.get("currency"),
                    }
                    for tx in recent_items
                ]

                xai_batch = safe_call(
                    "xAI batch prediction failed",
                    api_client.predict_anomaly_batch,
                    selected_user,
                    transactions=recent_payload,
                )

                if xai_batch:
                    predictions = xai_batch.get("predictions", [])
                    if not predictions:
                        st.info("No xAI predictions available.")
                    else:
                        for pred in predictions:
                            with st.expander(format_xai_prediction_title(pred)):
                                render_xai_prediction_details(pred)

    with tab_fhs:
        st.subheader("Financial Health Score")
        if not fhs:
            st.info("FHS is unavailable for this selection.")
        else:
            score_col, interpretation_col, summary_col = st.columns([1, 1, 2])
            score_col.metric("FHS Score", f"{float(fhs.get('score', 0)):.1f}")
            interpretation_col.metric("Interpretation", str(fhs.get("interpretation", "N/A")))
            summary_col.write(f"**Summary**\n\n{fhs.get('summary', '')}")

            st.markdown("#### Subscores")
            render_fhs_subscores(fhs)

            st.markdown("#### Top Drivers")
            drivers = fhs.get("top_drivers", [])
            if not drivers:
                st.info("No score drivers available.")
            else:
                for driver in drivers:
                    st.write(f"- **{driver.get('type', 'info').title()}**: {driver.get('message', '')}")

    with tab_profile:
        st.subheader("Behavior Profile")
        if not profile:
            st.info("Behavior profile is unavailable for this selection.")
        else:
            left, right = st.columns([1, 2])
            left.metric("Profile", str(profile.get("profile", "N/A")))
            left.metric("Distance to Centroid", f"{float(profile.get('distance_to_centroid', 0)):.4f}")
            right.write(f"**Explanation**\n\n{profile.get('explanation', '')}")

            st.markdown("#### Feature Vector")
            render_profile_feature_vector(profile)

    with tab_recommendations:
        st.subheader("Recommendations")
        render_recommendation_cards(recommendations)

    with tab_predict:
        st.subheader("Manual Anomaly Prediction")
        st.caption("Score a new transaction using the backend anomaly model and inspect top xAI factors.")
        if not selected_user:
            st.info("No user selected. Create a customer in the Add Customer tab.")
        else:
            with st.form("anomaly_predict_form"):
                col1, col2 = st.columns(2)
                occurred_date = col1.date_input("Occurred Date", value=date.today())
                occurred_time = col1.time_input("Occurred Time", value=time(12, 0))
                amount_value = col2.number_input("Amount", min_value=0.01, value=1000.0, step=100.0)

                col3, col4, col5 = st.columns(3)
                direction_value = col3.selectbox("Direction", options=["expense", "income", "debit", "credit"], index=0)
                category_value = col4.text_input("Category", value="Shopping").strip() or None
                currency_value = col5.text_input("Currency", value="LKR").strip() or None

                description_value = st.text_input("Description", value="Manual prediction scenario").strip() or None
                submitted = st.form_submit_button("Predict")

            if submitted:
                occurred_at_value = datetime.combine(occurred_date, occurred_time)
                occurred_at_iso = occurred_at_value.isoformat()
                prediction = safe_call(
                    "Prediction failed",
                    api_client.predict_anomaly,
                    selected_user,
                    occurred_at=occurred_at_iso,
                    amount=float(amount_value),
                    direction=direction_value,
                    category=category_value,
                    description=description_value,
                    currency=currency_value,
                )

                if prediction:
                    st.markdown("#### Prediction Result")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Risk Score", format_risk_score(prediction.get("risk_score", 0.0)))
                    col_b.metric("Threshold", format_risk_score(prediction.get("threshold", 0.5)))
                    col_c.metric(
                        "Predicted High Risk",
                        "Yes" if bool(prediction.get("predicted_is_high_risk", False)) else "No",
                    )

                    if not prediction.get("model_available", False):
                        st.warning("Model artifact is unavailable in backend. Train/export model first.")
                    else:
                        st.write(f"**Model:** {prediction.get('model_name', 'N/A')}")

                    factors = prediction.get("xai_factors", [])
                    st.markdown("#### xAI Factors")
                    render_xai_factors(factors)

    with tab_batch_predict:
        st.subheader("Batch Anomaly Prediction")
        if not selected_user:
            st.info("No user selected. Create a customer in the Add Customer tab.")
        st.write(
            "Add multiple transactions to score them with the anomaly model. "
            "Each transaction will show its risk score + xAI factors, "
            "and you'll receive recommendations based on the overall pattern."
        )

        # Initialize session state for transactions
        if "batch_transactions" not in st.session_state:
            st.session_state.batch_transactions = []

        # Add transaction form
        with st.form("add_transaction_form", clear_on_submit=True):
            st.markdown("##### Add Transaction")
            col1, col2 = st.columns(2)
            occurred_date = col1.date_input("Occurred Date", value=date.today())
            occurred_time = col2.time_input("Occurred Time", value=time(12, 0))

            col3, col4 = st.columns(2)
            amount_value = col3.number_input("Amount", min_value=0.01, value=1000.0, step=100.0)
            direction_value = col4.selectbox("Direction", ["expense", "income"], index=0)

            col5, col6, col7 = st.columns(3)
            category_value = col5.text_input("Category", value="Shopping").strip() or None
            currency_value = col6.text_input("Currency", value="LKR").strip() or None
            description_value = col7.text_input("Description", value="").strip() or None

            add_button = st.form_submit_button("Add Transaction")

        if add_button:
            occurred_at_value = datetime.combine(occurred_date, occurred_time)
            st.session_state.batch_transactions.append({
                "occurred_at": occurred_at_value.isoformat(),
                "amount": float(amount_value),
                "direction": direction_value,
                "category": category_value,
                "description": description_value,
                "currency": currency_value,
            })
            st.success(f"Added transaction #{len(st.session_state.batch_transactions)}")
            st.rerun()

        # Display current transactions
        if st.session_state.batch_transactions:
            st.markdown(f"##### Current Transactions ({len(st.session_state.batch_transactions)})")
            
            # Show transactions in a table
            for idx, tx in enumerate(st.session_state.batch_transactions):
                with st.expander(f"Transaction {idx + 1}: {tx['direction']} {tx['amount']} ({tx['category']})"):
                    st.json(tx)
                    if st.button(f"Remove #{idx + 1}", key=f"remove_{idx}"):
                        st.session_state.batch_transactions.pop(idx)
                        st.rerun()

            col_action1, col_action2 = st.columns(2)
            
            with col_action1:
                if st.button("Clear All", type="secondary"):
                    st.session_state.batch_transactions = []
                    st.rerun()

            with col_action2:
                if st.button("Predict Batch", type="primary"):
                    if not selected_user:
                        st.error("Select or create a user before running batch prediction.")
                        st.stop()
                    batch_result = safe_call(
                        "Batch prediction failed",
                        api_client.predict_anomaly_batch,
                        selected_user,
                        transactions=st.session_state.batch_transactions,
                    )

                    if batch_result:
                        st.markdown("---")
                        st.markdown("### Batch Prediction Results")

                        # Model info
                        col_m1, col_m2 = st.columns(2)
                        col_m1.metric("Model", batch_result.get("model_name", "N/A"))
                        col_m2.metric("Threshold", format_risk_score(batch_result.get("threshold", 0.5)))

                        if not batch_result.get("model_available", False):
                            st.warning("Model artifact unavailable. Train/export model first.")

                        # Individual predictions
                        st.markdown("#### Individual Transaction Predictions")
                        predictions = batch_result.get("predictions", [])
                        
                        if predictions:
                            for pred in predictions:
                                idx = pred.get("index", 0)
                                with st.expander(f"Transaction {idx + 1}: {format_xai_prediction_title(pred)}"):
                                    render_xai_prediction_details(pred)

                        # Recommendations
                        st.markdown("#### Recommendations")
                        recommendations = batch_result.get("recommendations", [])
                        
                        if recommendations:
                            for rec in recommendations:
                                priority = rec.get("priority", "medium")
                                priority_color = {
                                    "high": "🔴",
                                    "medium": "🟡",
                                    "low": "🟢",
                                }.get(priority, "⚪")
                                
                                with st.container():
                                    st.markdown(
                                        f"**{priority_color} #{rec.get('rank', 0)} - {rec.get('title', 'N/A')}**"
                                    )
                                    st.write(f"**Component:** {rec.get('component', 'N/A')}")
                                    st.write(f"**Message:** {rec.get('message', 'N/A')}")
                                    st.write(f"**Reason:** {rec.get('reason', 'N/A')}")
                                    if rec.get("estimated_impact"):
                                        st.write(f"**Estimated Impact:** {rec['estimated_impact']}")
                                    st.markdown("---")
                        else:
                            st.info("No recommendations generated. Your spending pattern looks healthy!")

        else:
            st.info("No transactions added yet. Use the form above to add transactions.")

    with tab_add_customer:
        st.subheader("Add Customer History")
        st.caption(
            "Create a new customer or extend an existing one with multiple income and expense records "
            "across several months for monthly comparison."
        )

        if "customer_history_transactions" not in st.session_state:
            st.session_state.customer_history_transactions = []
        if "customer_history_target_ref" not in st.session_state:
            st.session_state.customer_history_target_ref = selected_user or ""

        st.markdown("#### Add One Record")
        with st.form("tab_add_customer_history_record"):
            target_user_ref = st.text_input("Customer Ref", key="customer_history_target_ref").strip()

            col_h1, col_h2 = st.columns(2)
            history_date = col_h1.date_input("Occurred Date", value=date.today(), key="history_tx_date")
            history_time = col_h2.time_input("Occurred Time", value=time(12, 0), key="history_tx_time")

            col_h3, col_h4 = st.columns(2)
            history_amount = col_h3.number_input("Amount", min_value=0.01, value=100.0, step=10.0, key="history_tx_amount")
            history_direction = col_h4.selectbox(
                "Direction",
                options=["expense", "income"],
                index=0,
                key="history_tx_direction",
            )

            col_h5, col_h6 = st.columns(2)
            history_category = col_h5.text_input("Category", value="General", key="history_tx_category").strip() or None
            history_currency = col_h6.text_input("Currency", value="LKR", key="history_tx_currency").strip() or None

            history_description = st.text_input("Description", value="", key="history_tx_description").strip() or None
            add_history_submit = st.form_submit_button("Add Record")

        if add_history_submit:
            if not target_user_ref:
                st.error("Customer ref is required.")
            else:
                st.session_state.customer_history_transactions.append(
                    build_history_record(
                        user_ref=target_user_ref,
                        occurred_at=datetime.combine(history_date, history_time),
                        amount=float(history_amount),
                        direction=history_direction,
                        category=history_category,
                        description=history_description,
                        currency=history_currency,
                    )
                )
                st.success(f"Added record #{len(st.session_state.customer_history_transactions)} for {target_user_ref}.")
                st.rerun()

        st.markdown("#### Quick Start: 3-Month Starter History")
        col_q1, col_q2, col_q3 = st.columns(3)
        template_month = col_q1.date_input(
            "Anchor Month",
            value=date.today().replace(day=1),
            key="history_template_month",
        )
        template_income = col_q2.number_input(
            "Monthly Income",
            min_value=1000.0,
            value=120000.0,
            step=1000.0,
            key="history_template_income",
        )
        template_currency = col_q3.text_input("Template Currency", value="LKR", key="history_template_currency").strip() or "LKR"

        col_qb1, col_qb2 = st.columns(2)
        if col_qb1.button("Load 3-Month Starter History", type="secondary"):
            target_user_ref = st.session_state.get("customer_history_target_ref", "").strip()
            if not target_user_ref:
                st.error("Enter a customer ref first.")
            else:
                st.session_state.customer_history_transactions = build_starter_history(
                    user_ref=target_user_ref,
                    anchor_month=template_month.replace(day=1),
                    monthly_income=float(template_income),
                    currency=template_currency,
                )
                st.success(
                    f"Loaded {len(st.session_state.customer_history_transactions)} starter records for {target_user_ref} "
                    "including monthly income and expenses across three months."
                )
                st.rerun()

        if col_qb2.button("Clear Draft History", type="secondary"):
            st.session_state.customer_history_transactions = []
            st.rerun()

        draft_transactions = st.session_state.customer_history_transactions
        if draft_transactions:
            st.markdown(f"#### Draft History ({len(draft_transactions)} records)")

            draft_rows = []
            for idx, tx in enumerate(draft_transactions, start=1):
                draft_rows.append(
                    {
                        "#": idx,
                        "user_ref": tx.get("user_ref"),
                        "occurred_at": tx.get("occurred_at", "")[:16],
                        "direction": tx.get("direction"),
                        "category": tx.get("category") or "Uncategorized",
                        "amount": f"{float(tx.get('amount', 0.0)):,.2f}",
                        "currency": tx.get("currency") or "",
                    }
                )
            st.dataframe(draft_rows, use_container_width=True, hide_index=True)

            for idx, tx in enumerate(draft_transactions):
                label = (
                    f"Record {idx + 1}: {tx.get('occurred_at', '')[:10]} | "
                    f"{str(tx.get('direction', 'expense')).title()} | "
                    f"{float(tx.get('amount', 0.0)):,.2f} | "
                    f"{tx.get('category') or 'Uncategorized'}"
                )
                with st.expander(label):
                    st.json(tx)
                    if st.button(f"Remove Record #{idx + 1}", key=f"remove_customer_history_{idx}"):
                        st.session_state.customer_history_transactions.pop(idx)
                        st.rerun()

            if st.button("Ingest Customer History", type="primary"):
                ingest_payload = [
                    {
                        "external_tx_id": tx["external_tx_id"],
                        "user_ref": tx["user_ref"],
                        "occurred_at": tx["occurred_at"],
                        "amount": f"{float(tx['amount']):.2f}",
                        "direction": tx["direction"],
                        "category": tx.get("category"),
                        "description": tx.get("description"),
                        "currency": tx.get("currency"),
                    }
                    for tx in draft_transactions
                ]
                ingest_result = safe_call(
                    "Customer history ingestion failed",
                    api_client.ingest_transactions,
                    transactions=ingest_payload,
                )
                if ingest_result:
                    inserted = ingest_result.get("inserted", 0)
                    duplicates = ingest_result.get("duplicates", 0)
                    failed = ingest_result.get("failed", 0)
                    customer_refs = sorted({tx["user_ref"] for tx in draft_transactions})
                    if inserted > 0 and failed == 0:
                        st.success(
                            f"Ingested history for {', '.join(customer_refs)}. "
                            f"Result: {inserted} inserted, {duplicates} duplicates."
                        )
                        st.session_state.customer_history_transactions = []
                        st.cache_data.clear()
                        st.rerun()
                    elif failed > 0:
                        st.error(f"Ingestion failed for {failed} record(s): {ingest_result.get('errors', [])}")
                    else:
                        st.warning("All draft records already exist as duplicates.")
        else:
            st.info(
                "No draft history yet. Add records manually or load the 3-month starter history "
                "to create monthly income and expense data."
            )


if __name__ == "__main__":
    main()
