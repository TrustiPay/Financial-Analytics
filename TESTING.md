# Testing Guide

This project uses pytest with isolated SQLite fixtures for analytics/report logic.

## Prerequisites

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Automated Test Suites

- `tests/test_reports.py`
  - summary, categories, anomalies, features, FHS, recommendations unit/integration-style tests
- `tests/test_behavior_profile.py`
  - clustering preprocessing, profile assignment sanity, and behavior-profile endpoint tests
- `tests/test_users.py`
  - `/v1/users` list endpoint behavior and ordering
- `tests/test_demo_flow.py`
  - end-to-end API flow test using FastAPI `TestClient`

## Run Tests

Run all:

```bash
pytest -q
```

Run reports only:

```bash
pytest -q tests/test_reports.py
```

Run behavior-profile tests:

```bash
pytest -q tests/test_behavior_profile.py
```

Run users endpoint tests:

```bash
pytest -q tests/test_users.py
```

Run end-to-end demo flow only:

```bash
pytest -q tests/test_demo_flow.py
```

Verbose debugging:

```bash
pytest -vv
```

## End-to-End Flow Covered

`tests/test_demo_flow.py` validates this sequence in one test:
1. `POST /v1/ingest/transactions`
2. `GET /v1/users/{userRef}/transactions`
3. `GET /v1/users/{userRef}/reports/summary`
4. `GET /v1/users/{userRef}/reports/anomalies`
5. `GET /v1/users/{userRef}/reports/features`
6. `GET /v1/users/{userRef}/reports/fhs`
7. `GET /v1/users/{userRef}/reports/behavior-profile`
8. `GET /v1/users/{userRef}/reports/recommendations`

## Manual Verification Checklist

- App starts cleanly
- `/docs`, `/redoc`, `/openapi.json` load
- `/health` returns `database: ok`
- Ingestion works with valid key
- Ingestion rejects invalid key (`401`)
- Duplicate ingest produces duplicate counts
- Reports return deterministic payloads for the same data
