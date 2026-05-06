import os
from datetime import date, datetime
from typing import Any

import requests

API_BASE_URL = os.getenv("TRUSTIPAY_API_BASE_URL", "http://127.0.0.1:8005")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("TRUSTIPAY_API_TIMEOUT", "10"))
INGEST_KEY = os.getenv("TRUSTIPAY_INGEST_KEY", "change-me")


def _normalize_date_param(value: date | datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _compact_params(params: dict[str, Any]) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        compacted[key] = _normalize_date_param(value)
    return compacted


def _request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{API_BASE_URL.rstrip('/')}{path}"

    try:
        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Unable to reach API at {url}: {exc}") from exc

    if not response.ok:
        detail = response.text
        try:
            payload = response.json()
            detail = str(payload.get("detail", payload))
        except ValueError:
            pass
        raise RuntimeError(f"API call failed ({response.status_code}): {detail}")

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"API returned non-JSON response for {path}") from exc


def get_health() -> dict[str, Any]:
    return _request("GET", "/health")


def get_users() -> dict[str, Any]:
    return _request("GET", "/v1/users")


def get_transactions(
    user_ref: str,
    from_date: date | datetime | str | None = None,
    to_date: date | datetime | str | None = None,
    limit: int = 100,
    offset: int = 0,
    direction: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    params = _compact_params(
        {
            "from": from_date,
            "to": to_date,
            "limit": limit,
            "offset": offset,
            "direction": direction,
            "category": category,
        }
    )
    return _request("GET", f"/v1/users/{user_ref}/transactions", params=params)


def get_summary(
    user_ref: str,
    from_date: date | datetime | str | None = None,
    to_date: date | datetime | str | None = None,
    group_by: str = "month",
) -> dict[str, Any]:
    params = _compact_params({"from": from_date, "to": to_date, "groupBy": group_by})
    return _request("GET", f"/v1/users/{user_ref}/reports/summary", params=params)


def get_categories(
    user_ref: str,
    from_date: date | datetime | str | None = None,
    to_date: date | datetime | str | None = None,
) -> dict[str, Any]:
    params = _compact_params({"from": from_date, "to": to_date})
    return _request("GET", f"/v1/users/{user_ref}/reports/categories", params=params)


def get_anomalies(
    user_ref: str,
    from_date: date | datetime | str | None = None,
    to_date: date | datetime | str | None = None,
) -> dict[str, Any]:
    params = _compact_params({"from": from_date, "to": to_date})
    return _request("GET", f"/v1/users/{user_ref}/reports/anomalies", params=params)


def get_anomaly_impact(
    user_ref: str,
    month: str | None = None,
    from_date: date | datetime | str | None = None,
    to_date: date | datetime | str | None = None,
) -> dict[str, Any]:
    params = _compact_params({"month": month, "from": from_date, "to": to_date})
    return _request("GET", f"/v1/users/{user_ref}/reports/anomaly-impact", params=params)


def get_features(
    user_ref: str,
    month: str | None = None,
    from_date: date | datetime | str | None = None,
    to_date: date | datetime | str | None = None,
) -> dict[str, Any]:
    params = _compact_params({"month": month, "from": from_date, "to": to_date})
    return _request("GET", f"/v1/users/{user_ref}/reports/features", params=params)


def get_trends(
    user_ref: str,
    month: str | None = None,
    from_date: date | datetime | str | None = None,
    to_date: date | datetime | str | None = None,
    group_by: str = "week",
) -> dict[str, Any]:
    params = _compact_params({"month": month, "from": from_date, "to": to_date, "groupBy": group_by})
    return _request("GET", f"/v1/users/{user_ref}/reports/trends", params=params)


def get_fhs(
    user_ref: str,
    month: str | None = None,
    from_date: date | datetime | str | None = None,
    to_date: date | datetime | str | None = None,
) -> dict[str, Any]:
    params = _compact_params({"month": month, "from": from_date, "to": to_date})
    return _request("GET", f"/v1/users/{user_ref}/reports/fhs", params=params)


def get_behavior_profile(
    user_ref: str,
    month: str | None = None,
    from_date: date | datetime | str | None = None,
    to_date: date | datetime | str | None = None,
) -> dict[str, Any]:
    params = _compact_params({"month": month, "from": from_date, "to": to_date})
    return _request("GET", f"/v1/users/{user_ref}/reports/behavior-profile", params=params)


def get_recommendations(
    user_ref: str,
    month: str | None = None,
    from_date: date | datetime | str | None = None,
    to_date: date | datetime | str | None = None,
) -> dict[str, Any]:
    params = _compact_params({"month": month, "from": from_date, "to": to_date})
    return _request("GET", f"/v1/users/{user_ref}/reports/recommendations", params=params)


def predict_anomaly(
    user_ref: str,
    *,
    occurred_at: str,
    amount: float,
    direction: str,
    category: str | None,
    description: str | None,
    currency: str | None,
) -> dict[str, Any]:
    payload = {
        "occurred_at": occurred_at,
        "amount": amount,
        "direction": direction,
        "category": category,
        "description": description,
        "currency": currency,
    }
    return _request("POST", f"/v1/users/{user_ref}/reports/anomaly-predict", json_body=payload)


def predict_anomaly_batch(
    user_ref: str,
    *,
    transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Batch predict anomaly risk for multiple transactions.

    Args:
        user_ref: user identifier
        transactions: list of transaction dictionaries with keys:
            occurred_at, amount, direction, category, description, currency

    Returns:
        dict with keys: threshold, model_available, model_name, predictions, recommendations
    """
    payload = {"transactions": transactions}
    return _request("POST", f"/v1/users/{user_ref}/reports/anomaly-predict-batch", json_body=payload)


def ingest_transactions(
    *,
    transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    url = f"{API_BASE_URL.rstrip('/')}/v1/ingest/transactions"

    try:
        response = requests.post(
            url=url,
            json={"transactions": transactions},
            headers={"X-INGEST-KEY": INGEST_KEY, "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Unable to reach API at {url}: {exc}") from exc

    if not response.ok:
        detail = response.text
        try:
            payload = response.json()
            detail = str(payload.get("detail", payload))
        except ValueError:
            pass
        raise RuntimeError(f"Ingestion failed ({response.status_code}): {detail}")

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Ingestion endpoint returned non-JSON response") from exc
