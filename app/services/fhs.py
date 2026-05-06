from datetime import datetime

from app.schemas import FHSDriver, FHSFeatureSnapshot, FHSSubscore, ReportFHSResponse


def score_savings_ratio(value: float | None) -> tuple[float, str, str]:
    if value is None:
        return 0.0, "weak", "No income data was available to evaluate savings behavior."
    if value >= 0.40:
        return 35.0, "strong", "You saved a high share of your income during this period."
    if value >= 0.25:
        return 30.0, "strong", "You saved a healthy share of your income during this period."
    if value >= 0.10:
        return 22.0, "moderate", "Your savings ratio is positive but could be improved."
    if value >= 0.00:
        return 15.0, "moderate", "You maintained positive savings, but with limited buffer."
    if value >= -0.20:
        return 8.0, "weak", "Your expenses consumed most or all of your income."
    return 0.0, "weak", "Your expenses significantly exceeded your income."


def score_non_essential_ratio(value: float | None) -> tuple[float, str, str]:
    if value is None:
        return 12.0, "moderate", "No expense data was available, so this component is neutral."
    if value <= 0.10:
        return 25.0, "strong", "Only a small share of your expenses were non-essential."
    if value <= 0.20:
        return 22.0, "strong", "Your discretionary spending stayed at a low level."
    if value <= 0.35:
        return 17.0, "moderate", "A moderate share of your expenses were discretionary."
    if value <= 0.50:
        return 10.0, "moderate", "Discretionary spending took a noticeable share of expenses."
    if value <= 0.65:
        return 5.0, "weak", "A large share of your expenses were discretionary."
    return 0.0, "weak", "A very high share of your expenses were discretionary."


def score_spending_stability(value: float | None) -> tuple[float, str, str]:
    if value is None:
        return 12.0, "moderate", "Insufficient weekly data to evaluate spending stability."
    if value <= 0.10:
        return 25.0, "strong", "Your weekly expenses were consistent and predictable."
    if value <= 0.25:
        return 21.0, "strong", "Your weekly spending was mostly stable."
    if value <= 0.50:
        return 16.0, "moderate", "Your weekly spending showed moderate variability."
    if value <= 0.75:
        return 10.0, "moderate", "Your weekly spending fluctuated more than ideal."
    if value <= 1.00:
        return 5.0, "weak", "Your weekly spending was highly volatile."
    return 0.0, "weak", "Your weekly spending varied significantly across the period."


def score_anomaly_rate(value: float) -> tuple[float, str, str]:
    if value == 0:
        return 15.0, "strong", "No unusual spending anomalies were detected."
    if value <= 5:
        return 12.0, "strong", "Only a small number of unusual spending patterns were detected."
    if value <= 10:
        return 9.0, "moderate", "Some unusual spending patterns were detected."
    if value <= 20:
        return 5.0, "weak", "Frequent unusual spending patterns were detected."
    return 0.0, "weak", "Multiple unusual spending patterns were detected."


def interpret_total_score(total: float) -> tuple[str, str]:
    if total >= 80:
        return "Excellent", "Your spending behavior appears healthy and well controlled."
    if total >= 65:
        return "Stable", "Your finances look generally stable, with room for improvement."
    if total >= 50:
        return "Moderate", "Some financial habits need attention."
    if total >= 35:
        return "At Risk", "Your spending patterns indicate meaningful financial risk."
    return "Critical", "Immediate spending control and savings improvement are recommended."


def build_fhs(
    *,
    user_ref: str,
    from_dt: datetime,
    to_dt: datetime,
    features: dict,
) -> ReportFHSResponse:
    feature_snapshot = FHSFeatureSnapshot(
        income_total=features["income_total"],
        expense_total=features["expense_total"],
        net_total=features["net_total"],
        savings_ratio=features["savings_ratio"],
        non_essential_ratio=features["non_essential_ratio"],
        spending_stability=features["spending_stability"],
        anomaly_rate_per_100_tx=features["anomaly_rate_per_100_tx"],
    )

    if features.get("income_total", 0) == 0 and features.get("expense_total", 0) == 0:
        empty_subscores = [
            FHSSubscore(
                name="Savings Ratio",
                score=0.0,
                max_score=35.0,
                value=None,
                status="weak",
                reason="Insufficient transaction data for this component.",
            ),
            FHSSubscore(
                name="Non-Essential Spending",
                score=0.0,
                max_score=25.0,
                value=None,
                status="weak",
                reason="Insufficient transaction data for this component.",
            ),
            FHSSubscore(
                name="Spending Stability",
                score=0.0,
                max_score=25.0,
                value=None,
                status="weak",
                reason="Insufficient transaction data for this component.",
            ),
            FHSSubscore(
                name="Anomaly Risk",
                score=0.0,
                max_score=15.0,
                value=None,
                status="weak",
                reason="Insufficient transaction data for this component.",
            ),
        ]
        return ReportFHSResponse(
            user_ref=user_ref,
            from_=from_dt,
            to=to_dt,
            score=0.0,
            max_score=100.0,
            interpretation="Insufficient Data",
            summary="Insufficient transaction data to assess financial health reliably.",
            subscores=empty_subscores,
            top_drivers=[],
            feature_snapshot=feature_snapshot,
        )

    savings_score, savings_status, savings_reason = score_savings_ratio(features["savings_ratio"])
    non_essential_score, non_essential_status, non_essential_reason = score_non_essential_ratio(
        features["non_essential_ratio"]
    )
    stability_score, stability_status, stability_reason = score_spending_stability(
        features["spending_stability"]
    )
    anomaly_score, anomaly_status, anomaly_reason = score_anomaly_rate(
        float(features["anomaly_rate_per_100_tx"])
    )

    subscores = [
        FHSSubscore(
            name="Savings Ratio",
            score=savings_score,
            max_score=35.0,
            value=features["savings_ratio"],
            status=savings_status,
            reason=savings_reason,
        ),
        FHSSubscore(
            name="Non-Essential Spending",
            score=non_essential_score,
            max_score=25.0,
            value=features["non_essential_ratio"],
            status=non_essential_status,
            reason=non_essential_reason,
        ),
        FHSSubscore(
            name="Spending Stability",
            score=stability_score,
            max_score=25.0,
            value=features["spending_stability"],
            status=stability_status,
            reason=stability_reason,
        ),
        FHSSubscore(
            name="Anomaly Risk",
            score=anomaly_score,
            max_score=15.0,
            value=float(features["anomaly_rate_per_100_tx"]),
            status=anomaly_status,
            reason=anomaly_reason,
        ),
    ]

    total_score = round(sum(item.score for item in subscores), 2)
    interpretation, summary = interpret_total_score(total_score)
    top_drivers = _build_drivers(subscores)

    return ReportFHSResponse(
        user_ref=user_ref,
        from_=from_dt,
        to=to_dt,
        score=total_score,
        max_score=100.0,
        interpretation=interpretation,
        summary=summary,
        subscores=subscores,
        top_drivers=top_drivers,
        feature_snapshot=feature_snapshot,
    )


def _build_drivers(subscores: list[FHSSubscore]) -> list[FHSDriver]:
    ranked = sorted(subscores, key=lambda item: item.score / item.max_score)
    positive_ranked = sorted(subscores, key=lambda item: item.score / item.max_score, reverse=True)

    negative_messages = {
        "Savings Ratio": "Low savings ratio reduced your score.",
        "Non-Essential Spending": "High discretionary spending reduced your score.",
        "Spending Stability": "Weekly spending volatility reduced your score.",
        "Anomaly Risk": "Frequent anomalies reduced your score.",
    }
    positive_messages = {
        "Savings Ratio": "Your savings ratio improved your score.",
        "Non-Essential Spending": "Controlled discretionary spending improved your score.",
        "Spending Stability": "Consistent weekly spending improved your score.",
        "Anomaly Risk": "Your low anomaly rate improved your score.",
    }

    drivers: list[FHSDriver] = []
    for item in ranked[:2]:
        drivers.append(
            FHSDriver(
                type="negative",
                component=item.name,
                message=negative_messages[item.name],
            )
        )
    for item in positive_ranked[:1]:
        drivers.append(
            FHSDriver(
                type="positive",
                component=item.name,
                message=positive_messages[item.name],
            )
        )
    return drivers
