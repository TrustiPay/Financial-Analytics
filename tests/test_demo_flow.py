import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.deps import get_db
from app.main import app
import app.main as main_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "demo_flow.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setenv("INGEST_KEY", "test-ingest-key")
    monkeypatch.setattr(main_module, "init_db", lambda: None)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_demo_flow_end_to_end(client: TestClient) -> None:
    payload_path = Path("sample_data/demo_ingest.json")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    ingest_response = client.post(
        "/v1/ingest/transactions",
        headers={"X-INGEST-KEY": "test-ingest-key"},
        json=payload,
    )
    assert ingest_response.status_code == 200

    ingest_body = ingest_response.json()
    assert ingest_body["received"] == len(payload["transactions"])
    assert ingest_body["inserted"] == len(payload["transactions"])
    assert ingest_body["duplicates"] == 0
    assert ingest_body["failed"] == 0

    duplicate_response = client.post(
        "/v1/ingest/transactions",
        headers={"X-INGEST-KEY": "test-ingest-key"},
        json=payload,
    )
    assert duplicate_response.status_code == 200
    duplicate_body = duplicate_response.json()
    assert duplicate_body["inserted"] == 0
    assert duplicate_body["duplicates"] == len(payload["transactions"])

    user_ref = "demo-user-001"

    list_response = client.get(
        f"/v1/users/{user_ref}/transactions",
        params={"from": "2026-01-01", "to": "2026-03-31", "limit": 50, "offset": 0},
    )
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] >= 1
    assert list_body["count"] >= 1

    summary_response = client.get(
        f"/v1/users/{user_ref}/reports/summary",
        params={"from": "2026-01-01", "to": "2026-03-31", "groupBy": "month"},
    )
    assert summary_response.status_code == 200
    summary_body = summary_response.json()
    assert "income_total" in summary_body
    assert "expense_total" in summary_body
    assert "series" in summary_body

    anomalies_response = client.get(
        f"/v1/users/{user_ref}/reports/anomalies",
        params={"from": "2026-01-01", "to": "2026-03-31"},
    )
    assert anomalies_response.status_code == 200
    anomalies_body = anomalies_response.json()
    assert "anomaly_count" in anomalies_body
    assert "items" in anomalies_body

    features_response = client.get(
        f"/v1/users/{user_ref}/reports/features",
        params={"month": "2026-03"},
    )
    assert features_response.status_code == 200
    features_body = features_response.json()
    assert "savings_ratio" in features_body
    assert "anomaly_rate_per_100_tx" in features_body

    fhs_response = client.get(
        f"/v1/users/{user_ref}/reports/fhs",
        params={"month": "2026-03"},
    )
    assert fhs_response.status_code == 200
    fhs_body = fhs_response.json()
    assert isinstance(fhs_body["score"], (int, float))
    assert 0 <= fhs_body["score"] <= 100
    assert "subscores" in fhs_body
    assert "top_drivers" in fhs_body

    behavior_profile_response = client.get(
        f"/v1/users/{user_ref}/reports/behavior-profile",
        params={"month": "2026-03"},
    )
    assert behavior_profile_response.status_code == 200
    behavior_profile_body = behavior_profile_response.json()
    assert "profile" in behavior_profile_body
    assert "cluster_id" in behavior_profile_body
    assert "distance_to_centroid" in behavior_profile_body
    assert "feature_vector" in behavior_profile_body

    recommendations_response = client.get(
        f"/v1/users/{user_ref}/reports/recommendations",
        params={"month": "2026-03"},
    )
    assert recommendations_response.status_code == 200
    recommendations_body = recommendations_response.json()
    assert "fhs_score" in recommendations_body
    assert "interpretation" in recommendations_body
    assert recommendations_body["items"]
