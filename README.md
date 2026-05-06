# TrustiPay Analytics & Scoring Service

TrustiPay analytics component that ingests wallet transactions, stores derived analytics data, and exposes deterministic reports and insights.

Core capabilities:
- transaction ingestion (idempotent)
- verification/read APIs
- summary and category reporting
- hybrid anomaly detection (statistical + ML risk model)
- feature engineering
- Financial Health Score (FHS)
- behavior profiling with KMeans clustering
- rule-based recommendations
- Streamlit dashboard (API-driven)

Wallet remains the source of truth for transaction creation.

## Prerequisites

- Python 3.11+
- `pip`
- `venv`

## Setup

1. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
```

4. Update values if needed:
- `INGEST_KEY=change-me`
- `DB_URL=sqlite:///./trustipay.db`

## Run Backend API

```bash
uvicorn app.main:app --reload
```

Endpoints:
- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`

## Run Streamlit Dashboard

Backend must be running first.

```bash
streamlit run dashboard/dashboard.py
```

Dashboard features:
- sidebar backend status
- API-driven user dropdown via `GET /v1/users`
- month + date-range selectors
- overview metrics
- transactions table
- reports charts (summary/categories)
- FHS and profile visualization
- recommendation cards

## Demo Data Seeding

Stable demo user: `demo-user-001`

### Option A: seed script (recommended)

```bash
python scripts/seed_demo.py --base-url http://127.0.0.1:8000 --ingest-key change-me
```

Default payload file: `sample_data/demo_ingest.json`

### Option B: Swagger manual ingest

Use `POST /v1/ingest/transactions` with:
- header: `X-INGEST-KEY: <INGEST_KEY>`
- body: `sample_data/demo_ingest.json`

## API Surface

- `GET /health`
- `GET /v1/users`
- `POST /v1/ingest/transactions`
- `GET /v1/users/{userRef}/transactions`
- `GET /v1/users/{userRef}/transactions/{txId}`
- `GET /v1/users/{userRef}/reports/summary`
- `GET /v1/users/{userRef}/reports/categories`
- `GET /v1/users/{userRef}/reports/anomalies`
- `GET /v1/users/{userRef}/reports/features`
- `GET /v1/users/{userRef}/reports/fhs`
- `GET /v1/users/{userRef}/reports/behavior-profile`
- `GET /v1/users/{userRef}/reports/recommendations`

## Behavior Profiling (ML)

Behavior profile endpoint uses unsupervised learning:
- features: `savings_ratio`, `non_essential_ratio`, `spending_stability`, `anomaly_rate_per_100_tx`
- imputation for missing values (deterministic defaults)
- `StandardScaler` normalization
- `KMeans(k=4, random_state=42, n_init=10)`
- centroid-based label mapping:
  - Conservative Saver
  - Balanced Spender
  - Lifestyle Spender
  - Volatile Risk User

## Architecture

```text
Wallet / Group Integration
        ↓
FastAPI Analytics Service
        ├── Swagger
        ├── Streamlit Dashboard
        └── External API Consumers
```

Detailed analytics pipeline:

```text
Wallet Transactions
    ↓
Ingestion API
    ↓
SQLite Analytics Store
    ↓
Feature Engineering
    ↓
├── Statistical Anomaly Detection
├── ML Anomaly Risk Scoring (when artifact available)
├── Financial Health Score
├── Behavior Profiling (KMeans Clustering)
└── Recommendations
```

## Notebooks

- `notebook/trustipay_anomaly_risk_xai.ipynb` - supervised anomaly risk model training + xAI
- `notebook/trustipay_ml_xai.ipynb` - supervised direction classification workflow + xAI
- `notebook/trustipay_behavior_profile_kmeans.ipynb` - KMeans behavior profiling analysis
- `notebook/trustipay_backend_api_integration.ipynb` - end-to-end backend API integration checks

## Project Structure

- `app/routers/` route wiring and validation
- `app/services/` business logic
  - `features.py` raw metrics
  - `fhs.py` scoring
  - `behavior_profile.py` clustering profile
  - `recommendations.py` actions
- `dashboard/` Streamlit frontend
  - `dashboard.py` app orchestration
  - `api_client.py` backend API wrappers
  - `components.py` reusable UI renderers

## Testing

Run all tests:

```bash
pytest -q
```

Run selected suites:

```bash
pytest -q tests/test_reports.py
pytest -q tests/test_behavior_profile.py
pytest -q tests/test_demo_flow.py
```
# Financial-Analytics
