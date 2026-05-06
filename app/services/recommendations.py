from decimal import Decimal, ROUND_HALF_UP

from app.schemas import RecommendationItem, ReportFHSResponse

PRIORITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
COMPONENT_ORDER = {
    "savings_ratio": 0,
    "non_essential_ratio": 1,
    "spending_stability": 2,
    "anomaly_risk": 3,
    "general": 4,
}

SAVINGS_RATIO_TRIGGER = 0.10
SAVINGS_RATIO_NEGATIVE = 0.0

NON_ESSENTIAL_RATIO_TRIGGER = 0.35
NON_ESSENTIAL_RATIO_HIGH = 0.50
NON_ESSENTIAL_REDUCTION_FACTOR = Decimal("0.10")

SPENDING_STABILITY_TRIGGER = 0.50
SPENDING_STABILITY_HIGH = 0.75

ANOMALY_RATE_TRIGGER = 5.0
ANOMALY_RATE_HIGH = 10.0
ANOMALY_COUNT_HIGH = 3

FHS_STRONG_THRESHOLD = 80.0


def build_recommendations(
    *,
    features: dict,
    fhs_result: ReportFHSResponse,
    max_items: int = 5,
) -> list[RecommendationItem]:
    recommendations: list[RecommendationItem] = []

    if fhs_result.interpretation == "Insufficient Data":
        recommendations.append(
            RecommendationItem(
                title="Add more transaction data",
                priority="low",
                component="general",
                message="Add more transaction data to receive personalized recommendations.",
                reason="There is not enough transaction data to generate meaningful recommendations.",
                estimated_impact="With more transaction history, recommendations can better target your weak areas.",
                action_type="collect_data",
                rank=0,
            )
        )
        return _rank_and_limit(recommendations, max_items=max_items)

    savings_ratio = features.get("savings_ratio")
    non_essential_ratio = features.get("non_essential_ratio")
    spending_stability = features.get("spending_stability")
    anomaly_count = int(features.get("anomaly_count", 0))
    anomaly_rate = float(features.get("anomaly_rate_per_100_tx", 0.0))
    non_essential_total = Decimal(features.get("non_essential_expense_total", Decimal("0")))

    if savings_ratio is None or savings_ratio < SAVINGS_RATIO_TRIGGER:
        priority = (
            "high"
            if (savings_ratio is not None and savings_ratio < SAVINGS_RATIO_NEGATIVE)
            else "medium"
        )
        impact = (
            "Moving from negative savings to at least break-even could meaningfully improve your FHS."
            if savings_ratio is not None and savings_ratio < SAVINGS_RATIO_NEGATIVE
            else (
                f"Increasing savings above {int(SAVINGS_RATIO_TRIGGER * 100)}% "
                "could improve your savings subscore."
            )
        )
        recommendations.append(
            RecommendationItem(
                title="Improve monthly savings",
                priority=priority,
                component="savings_ratio",
                message="Try to keep at least 10% of your income unspent each month.",
                reason="Your savings ratio is currently low, which significantly reduced your score.",
                estimated_impact=impact,
                action_type="increase_savings",
                rank=0,
            )
        )

    if non_essential_ratio is not None and non_essential_ratio > NON_ESSENTIAL_RATIO_TRIGGER:
        priority = "high" if non_essential_ratio > NON_ESSENTIAL_RATIO_HIGH else "medium"
        reduction_target = (non_essential_total * NON_ESSENTIAL_REDUCTION_FACTOR).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        recommendations.append(
            RecommendationItem(
                title="Reduce discretionary spending",
                priority=priority,
                component="non_essential_ratio",
                message=(
                    "A large share of your spending is discretionary. "
                    "Consider reducing shopping or entertainment expenses by 10-15%."
                ),
                reason="High discretionary spending lowered your non-essential spending score.",
                estimated_impact=(
                    "Reducing non-essential spending by about 10% "
                    f"(around {reduction_target}) may improve your score and free more money for savings."
                ),
                action_type="reduce_spending",
                rank=0,
            )
        )

    if spending_stability is not None and spending_stability > SPENDING_STABILITY_TRIGGER:
        priority = "high" if spending_stability > SPENDING_STABILITY_HIGH else "medium"
        recommendations.append(
            RecommendationItem(
                title="Stabilize weekly spending",
                priority=priority,
                component="spending_stability",
                message=(
                    "Your weekly expenses vary significantly. "
                    "Set weekly spending limits to make cash flow more predictable."
                ),
                reason="High variation in weekly spending reduced your stability subscore.",
                estimated_impact="Reducing sharp weekly spikes could improve your stability score.",
                action_type="stabilize_spending",
                rank=0,
            )
        )

    if anomaly_count > 0 or anomaly_rate > ANOMALY_RATE_TRIGGER:
        priority = (
            "high"
            if anomaly_rate > ANOMALY_RATE_HIGH or anomaly_count >= ANOMALY_COUNT_HIGH
            else "medium"
        )
        recommendations.append(
            RecommendationItem(
                title="Review unusual transactions",
                priority=priority,
                component="anomaly_risk",
                message=(
                    "You have unusual spending patterns in this period. "
                    "Review high-value or irregular transactions to identify avoidable spikes."
                ),
                reason="Detected anomalies reduced your anomaly risk score.",
                estimated_impact=(
                    "Avoiding repeated unusual expenses could improve your score and reduce volatility."
                ),
                action_type="review_anomalies",
                rank=0,
            )
        )

    if fhs_result.score >= FHS_STRONG_THRESHOLD:
        recommendations.append(
            RecommendationItem(
                title="Maintain current discipline",
                priority="low",
                component="general",
                message=(
                    "Your financial habits are strong overall. "
                    "Maintain your current savings and spending discipline to keep your score high."
                ),
                reason="Your score is already in a healthy range.",
                estimated_impact="Maintaining this pattern can help preserve your high score.",
                action_type="maintain_habits",
                rank=0,
            )
        )

    if not recommendations:
        recommendations.append(
            RecommendationItem(
                title="Maintain current discipline",
                priority="low",
                component="general",
                message=(
                    "Your current behavior is reasonably balanced. "
                    "Continue monitoring spending and maintain a healthy savings buffer."
                ),
                reason="No major risk signals were detected in this period.",
                estimated_impact="Maintaining these habits should help keep your score stable.",
                action_type="maintain_habits",
                rank=0,
            )
        )

    return _rank_and_limit(recommendations, max_items=max_items)


def _rank_and_limit(items: list[RecommendationItem], max_items: int) -> list[RecommendationItem]:
    sorted_items = sorted(
        items,
        key=lambda item: (
            -PRIORITY_WEIGHT.get(item.priority, 0),
            COMPONENT_ORDER.get(item.component, 99),
            item.title.lower(),
        ),
    )

    for index, item in enumerate(sorted_items, start=1):
        item.rank = index

    return sorted_items[:max_items]
