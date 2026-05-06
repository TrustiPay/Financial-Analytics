# AGENTS.md — Contributor & Integration Guide

This repository contains the **Analytics & Scoring** component for TrustiPay.

## Ownership and Boundaries

- Wallet team owns:
  - wallet/payment transaction creation
  - wallet database and transaction truth
- This service owns:
  - ingestion of completed wallet transactions
  - derived analytics storage
  - read-only reports
  - Financial Health Score (FHS)
  - behavior profiling
  - recommendations
  - Streamlit dashboard for presentation

Wallet remains the source of truth. This service must not mutate wallet transactions.

## Integration Contract

### Ingestion mode

Wallet pushes completed transactions to:
- `POST /v1/ingest/transactions`

Required header:
- `X-INGEST-KEY: <shared-secret>`

If the key is missing or invalid, API returns `401 Unauthorized`.

### Required transaction fields

Wallet should send for each transaction:
- `external_tx_id` (wallet-unique ID)
- `user_ref` (wallet user identifier)
- `occurred_at` (ISO timestamp)
- `amount` (numeric)
- `direction` (`expense|income` or `debit|credit`)

Optional but recommended:
- `category`
- `description`
- `currency`

### Idempotency

The service enforces idempotency via:
- unique key: `(source, external_tx_id)`

Behavior:
- repeated sends of the same transaction are safe
- duplicates are counted and skipped
- batch processing should continue for valid records

## Data Normalization Rules

- `debit -> expense`
- `credit -> income`
- store timestamps consistently in UTC/naive UTC
- store amounts as numeric values

## Behavioral Profiling Capability

This service derives a user behavior profile internally using unsupervised clustering on analytics features.

- Wallet teams do not provide profile labels.
- Profiles are derived from analytics data only.
- Wallet remains source-of-truth only for raw transactions.

## Streamlit Dashboard Rules

The Streamlit dashboard is presentation-only.

- It must consume the FastAPI endpoints.
- It must not read SQLite directly.
- User selection must come from API user list (`GET /v1/users`).
- Dashboard logic should not duplicate backend analytics/scoring logic.

## Read-Only Reporting Endpoints

Consumers (wallet UI/backend/dashboard) should read from:
- `/v1/users/{userRef}/reports/summary`
- `/v1/users/{userRef}/reports/categories`
- `/v1/users/{userRef}/reports/anomalies`
- `/v1/users/{userRef}/reports/features`
- `/v1/users/{userRef}/reports/fhs`
- `/v1/users/{userRef}/reports/behavior-profile`
- `/v1/users/{userRef}/reports/recommendations`

All report endpoints are deterministic for the same input data.

## Error Handling Expectations

- Validation errors: `400`
- Auth errors: `401`
- Missing transaction by ID: `404`
- Unknown user with no data (reports/list): `200` with empty datasets
- Ingestion supports partial success counters (`inserted`, `duplicates`, `failed`)

## Local Development

1. Create venv and install dependencies
2. Copy `.env.example` to `.env`
3. Set `INGEST_KEY` and `DB_URL`
4. Run API:

```bash
uvicorn app.main:app --reload
```

5. Run dashboard:

```bash
streamlit run dashboard/dashboard.py
```

## Architecture

```text
Wallet / Group Integration
        ↓
FastAPI Analytics Service
        ├── Swagger
        ├── Streamlit Dashboard
        └── External API Consumers
```

## Contribution Guidelines

- Keep routers thin (validation + service calls + schemas)
- Keep analytics/scoring logic inside `app/services/`
- Keep ML profiling logic isolated in `app/services/behavior_profile.py`
- Keep dashboard logic in `dashboard/` with API-only data access
- Add tests for analytics behavior and edge cases
- Keep endpoint contracts explicit with response models and examples

## Definition of Done

- Wallet can push batches successfully
- Duplicate re-sends are handled safely
- Analytics DB persists normalized transactions
- Reports, FHS, behavior profiles, and recommendations are explainable
- Dashboard consumes APIs correctly with user dropdown + filters
- Demo flow is reproducible on a fresh machine
