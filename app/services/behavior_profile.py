from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from app.schemas import BehaviorFeatureVector, ReportBehaviorProfileResponse

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
except Exception:  # pragma: no cover - handled at runtime if dependency is missing
    KMeans = None  # type: ignore[assignment]
    StandardScaler = None  # type: ignore[assignment]

FEATURE_ORDER = (
    "savings_ratio",
    "non_essential_ratio",
    "spending_stability",
    "anomaly_rate_per_100_tx",
)
KMEANS_CLUSTER_COUNT = 4
KMEANS_RANDOM_STATE = 42
KMEANS_N_INIT = 10

IMPUTED_DEFAULTS = {
    "savings_ratio": 0.0,
    "non_essential_ratio": 0.0,
    "spending_stability": 0.5,
    "anomaly_rate_per_100_tx": 0.0,
}

PROFILE_EXPLANATIONS = {
    "Conservative Saver": (
        "This profile reflects strong savings behavior, controlled discretionary spending, "
        "and stable weekly expenses."
    ),
    "Balanced Spender": (
        "This profile reflects moderate savings, balanced discretionary spending, "
        "and relatively stable financial behavior."
    ),
    "Lifestyle Spender": (
        "This profile reflects lower savings and a higher share of discretionary spending, "
        "often associated with lifestyle-driven expense patterns."
    ),
    "Volatile Risk User": (
        "This profile reflects unstable weekly spending, weaker savings behavior, "
        "and elevated irregular transaction risk."
    ),
}

REFERENCE_VECTORS = [
    [0.46, 0.08, 0.12, 0.0],
    [0.40, 0.10, 0.16, 1.0],
    [0.35, 0.14, 0.18, 2.0],
    [0.33, 0.12, 0.20, 1.5],
    [0.24, 0.22, 0.30, 3.0],
    [0.18, 0.26, 0.32, 4.0],
    [0.14, 0.28, 0.36, 4.5],
    [0.10, 0.30, 0.40, 5.0],
    [0.06, 0.48, 0.54, 8.0],
    [0.02, 0.58, 0.50, 9.5],
    [0.00, 0.62, 0.46, 10.5],
    [-0.02, 0.55, 0.60, 11.0],
    [-0.10, 0.40, 0.90, 18.0],
    [-0.18, 0.45, 1.00, 20.0],
    [-0.25, 0.55, 1.12, 22.0],
    [-0.15, 0.50, 0.95, 19.0],
]

_ARTIFACTS: "BehaviorModelArtifacts | None" = None


@dataclass
class BehaviorModelArtifacts:
    scaler: Any
    model: Any
    label_map: dict[int, str]


def preprocess_feature_vector(features: dict[str, Any]) -> BehaviorFeatureVector:
    return BehaviorFeatureVector(
        savings_ratio=_safe_float(features.get("savings_ratio"), IMPUTED_DEFAULTS["savings_ratio"]),
        non_essential_ratio=_safe_float(
            features.get("non_essential_ratio"),
            IMPUTED_DEFAULTS["non_essential_ratio"],
        ),
        spending_stability=_safe_float(
            features.get("spending_stability"),
            IMPUTED_DEFAULTS["spending_stability"],
        ),
        anomaly_rate_per_100_tx=_safe_float(
            features.get("anomaly_rate_per_100_tx"),
            IMPUTED_DEFAULTS["anomaly_rate_per_100_tx"],
        ),
    )


def build_behavior_profile(
    *,
    user_ref: str,
    from_dt: datetime,
    to_dt: datetime,
    features: dict[str, Any],
) -> ReportBehaviorProfileResponse:
    feature_vector = preprocess_feature_vector(features)
    if _is_no_data(features):
        return ReportBehaviorProfileResponse(
            user_ref=user_ref,
            from_=from_dt,
            to=to_dt,
            profile="Insufficient Data",
            cluster_id=-1,
            distance_to_centroid=0.0,
            feature_vector=feature_vector,
            explanation=(
                "Not enough transaction data is available to generate a reliable behavior profile."
            ),
        )

    artifacts = _get_behavior_model_artifacts()
    vector = np.array(
        [
            feature_vector.savings_ratio,
            feature_vector.non_essential_ratio,
            feature_vector.spending_stability,
            feature_vector.anomaly_rate_per_100_tx,
        ],
        dtype=float,
    )
    scaled_vector = artifacts.scaler.transform([vector])[0]
    cluster_id = int(artifacts.model.predict([scaled_vector])[0])
    centroid = artifacts.model.cluster_centers_[cluster_id]
    distance = float(np.linalg.norm(scaled_vector - centroid))

    profile = artifacts.label_map.get(cluster_id, "Balanced Spender")
    explanation = _build_profile_explanation(profile, feature_vector)

    return ReportBehaviorProfileResponse(
        user_ref=user_ref,
        from_=from_dt,
        to=to_dt,
        profile=profile,
        cluster_id=cluster_id,
        distance_to_centroid=round(distance, 4),
        feature_vector=feature_vector,
        explanation=explanation,
    )


def _get_behavior_model_artifacts() -> BehaviorModelArtifacts:
    global _ARTIFACTS
    if _ARTIFACTS is None:
        _ARTIFACTS = fit_behavior_model()
    return _ARTIFACTS


def fit_behavior_model() -> BehaviorModelArtifacts:
    if KMeans is None or StandardScaler is None:
        raise RuntimeError("scikit-learn is required for behavior profiling.")

    vectors = np.array(REFERENCE_VECTORS, dtype=float)
    scaler = StandardScaler()
    scaled_vectors = scaler.fit_transform(vectors)

    model = KMeans(
        n_clusters=KMEANS_CLUSTER_COUNT,
        random_state=KMEANS_RANDOM_STATE,
        n_init=KMEANS_N_INIT,
    )
    model.fit(scaled_vectors)

    centroids_original_scale = scaler.inverse_transform(model.cluster_centers_)
    label_map = _build_cluster_label_map(centroids_original_scale)
    return BehaviorModelArtifacts(scaler=scaler, model=model, label_map=label_map)


def _build_cluster_label_map(centroids: np.ndarray) -> dict[int, str]:
    remaining = set(range(len(centroids)))

    conservative_idx = max(
        remaining,
        key=lambda i: (
            centroids[i][0],
            -centroids[i][1],
            -centroids[i][2],
            -centroids[i][3],
        ),
    )
    remaining.remove(conservative_idx)

    volatile_risk_idx = max(
        remaining,
        key=lambda i: (
            centroids[i][2] + (centroids[i][3] * 0.04) - centroids[i][0],
            centroids[i][3],
            centroids[i][2],
        ),
    )
    remaining.remove(volatile_risk_idx)

    lifestyle_idx = max(
        remaining,
        key=lambda i: (
            centroids[i][1] - centroids[i][0],
            centroids[i][1],
            centroids[i][3],
        ),
    )
    remaining.remove(lifestyle_idx)

    balanced_idx = remaining.pop()

    return {
        conservative_idx: "Conservative Saver",
        balanced_idx: "Balanced Spender",
        lifestyle_idx: "Lifestyle Spender",
        volatile_risk_idx: "Volatile Risk User",
    }


def _build_profile_explanation(profile: str, vector: BehaviorFeatureVector) -> str:
    base = PROFILE_EXPLANATIONS.get(
        profile,
        "This profile reflects the observed behavior pattern from your selected transaction period.",
    )
    dynamic_bits: list[str] = []

    if vector.savings_ratio < 0:
        dynamic_bits.append("Savings are negative in this period")
    elif vector.savings_ratio >= 0.25:
        dynamic_bits.append("Savings behavior is relatively strong")

    if vector.non_essential_ratio > 0.35:
        dynamic_bits.append("discretionary spending share is elevated")

    if vector.spending_stability > 0.5:
        dynamic_bits.append("weekly spending volatility is high")

    if vector.anomaly_rate_per_100_tx > 5:
        dynamic_bits.append("anomaly frequency is above baseline")

    if not dynamic_bits:
        return base

    return f"{base} Key signals: " + "; ".join(dynamic_bits) + "."


def _safe_float(value: Any, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _is_no_data(features: dict[str, Any]) -> bool:
    income_total = _safe_float(features.get("income_total"), 0.0)
    expense_total = _safe_float(features.get("expense_total"), 0.0)
    total_tx = int(features.get("expense_tx_count", 0)) + int(features.get("anomaly_count", 0))
    return income_total == 0.0 and expense_total == 0.0 and total_tx == 0
